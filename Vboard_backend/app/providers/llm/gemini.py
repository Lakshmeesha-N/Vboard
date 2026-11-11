"""
app/providers/llm/gemini.py

Google Gemini LLM provider.

Implements the BaseLLMProvider protocol using the Google GenAI REST API
via httpx.  This avoids adding the google-genai SDK as a mandatory
dependency while keeping the provider fully functional.

Requires settings.GEMINI_API_KEY to be set.

Structured output (response_format) is mapped to Gemini's
response_mime_type + response_schema when the format is a JSON schema.
Tool definitions are mapped to Gemini FunctionDeclarations.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import httpx
from loguru import logger

from app.core.exceptions import MetaApiError, RateLimitedError
from app.services.llm_service import LLMResult

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _openai_tools_to_gemini(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert an OpenAI-style tool list to Gemini FunctionDeclaration format.

    OpenAI format:
        [{"type": "function", "function": {"name": ..., "description": ...,
          "parameters": {...}}}]

    Gemini format (inside a Tool object):
        [{"functionDeclarations": [{"name": ..., "description": ...,
           "parameters": {...}}]}]
    """
    declarations = []
    for tool in tools:
        fn = tool.get("function", {})
        decl: dict[str, Any] = {"name": fn.get("name", "")}
        if fn.get("description"):
            decl["description"] = fn["description"]
        if fn.get("parameters"):
            decl["parameters"] = fn["parameters"]
        declarations.append(decl)
    return [{"functionDeclarations": declarations}]


def _strip_unsupported_schema_fields(schema: Any) -> Any:
    """Recursively remove JSON Schema keys unsupported by Gemini responseSchema."""
    if isinstance(schema, dict):
        return {
            k: _strip_unsupported_schema_fields(v)
            for k, v in schema.items()
            if k != "additionalProperties"
        }
    if isinstance(schema, list):
        return [_strip_unsupported_schema_fields(item) for item in schema]
    return schema


def _openai_messages_to_gemini(
    messages: list[dict[str, Any]],
) -> tuple[Optional[str], list[dict[str, Any]]]:
    """
    Convert OpenAI-style messages to Gemini's system_instruction + contents format.

    Returns:
        (system_instruction_text, gemini_contents_list)
    """
    system_text: Optional[str] = None
    contents: list[dict[str, Any]] = []
    call_id_to_name: dict[str, str] = {}

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content")

        if role == "system":
            system_text = content or ""
            continue

        if role == "user":
            gemini_role = "user"
        elif role == "assistant":
            gemini_role = "model"
        elif role == "tool":
            # Tool result → function response part
            tool_call_id = msg.get("tool_call_id", "tool_call")
            fn_name = (
                call_id_to_name.get(tool_call_id)
                or msg.get("name")
                or tool_call_id
            )
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": fn_name,
                                "response": {"content": content or ""},
                            }
                        }
                    ],
                }
            )
            continue
        else:
            gemini_role = "user"

        # Handle assistant messages that contain tool_calls
        tool_calls = msg.get("tool_calls")
        if tool_calls and gemini_role == "model":
            parts = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name", "")
                tc_id = tc.get("id")
                if tc_id and fn_name:
                    call_id_to_name[str(tc_id)] = fn_name
                args_str = fn.get("arguments", "{}")
                try:
                    args = (
                        json.loads(args_str)
                        if isinstance(args_str, str)
                        else args_str
                    )
                except Exception:
                    args = {}
                parts.append(
                    {
                        "functionCall": {
                            "name": fn_name,
                            "args": args,
                        }
                    }
                )
            contents.append({"role": gemini_role, "parts": parts})
            continue

        if content is None:
            continue

        contents.append(
            {"role": gemini_role, "parts": [{"text": content}]}
        )

    return system_text, contents


def _extract_gemini_result(
    data: dict[str, Any], elapsed_ms: float
) -> LLMResult:
    """
    Parse a Gemini generateContent response dict into an LLMResult.

    Handles both text responses and functionCall responses.
    """
    text = ""
    tool_calls: list[Any] = []

    candidates = data.get("candidates", [])
    if candidates:
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        for part in parts:
            if "text" in part:
                text += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                # Normalize to OpenAI-style tool call dict for compatibility
                tool_calls.append(
                    {
                        "id": "gemini_call_1",
                        "type": "function",
                        "function": {
                            "name": fc.get("name", ""),
                            "arguments": json.dumps(fc.get("args", {})),
                        },
                    }
                )

    usage = data.get("usageMetadata", {})
    prompt_tokens = int(usage.get("promptTokenCount", 0))
    completion_tokens = int(usage.get("candidatesTokenCount", 0))

    elapsed_rounded = round(elapsed_ms, 2)

    logger.info(
        "LLM complete (gemini): elapsed_ms={:.2f}, prompt_tokens={}, "
        "completion_tokens={}, tool_calls={}",
        elapsed_rounded,
        prompt_tokens,
        completion_tokens,
        len(tool_calls),
    )

    return LLMResult(
        text=text,
        elapsed_ms=elapsed_rounded,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=0,
        reasoning_tokens=0,
        tool_calls=tool_calls,
    )


class GoogleGeminiLLMProvider:
    """
    LLM provider backed by the Google Gemini generateContent REST API.

    Args:
        api_key: Google AI Studio / Cloud API key.
        model: Gemini model name (e.g. "gemini-2.5-flash").
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 25.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._base = _GEMINI_BASE

    async def _post(self, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST to a Gemini endpoint and normalize errors."""
        url = f"{self._base}/{endpoint}?key={self._api_key}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=5.0)
            ) as client:
                resp = await client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise MetaApiError(f"Gemini API connection error: {exc}") from None

        if resp.status_code == 200:
            try:
                return resp.json()
            except Exception:
                raise MetaApiError(
                    "Failed to parse Gemini API response", status_code=200
                )
        if resp.status_code == 429:
            raise RateLimitedError("Gemini API rate limit exceeded")
        if resp.status_code in (500, 503):
            raise MetaApiError("Gemini API server error", status_code=resp.status_code)
        raise MetaApiError(
            f"Gemini API request failed with status {resp.status_code}",
            status_code=resp.status_code,
        )

    async def complete(
        self,
        system_prompt: str,
        user_text: str,
        response_format: Optional[dict[str, Any]] = None,
        reasoning_effort: Optional[str] = None,
    ) -> LLMResult:
        """Single-turn system+user chat completion via Gemini."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
        return await self.complete_messages(
            messages, response_format=response_format
        )

    async def complete_messages(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        response_format: Optional[dict[str, Any]] = None,
        reasoning_effort: Optional[str] = None,
    ) -> LLMResult:
        """Multi-turn chat completion with optional function-calling via Gemini."""
        system_text, contents = _openai_messages_to_gemini(messages)

        body: dict[str, Any] = {"contents": contents}

        if system_text:
            body["systemInstruction"] = {
                "parts": [{"text": system_text}]
            }

        # Map OpenAI tools to Gemini FunctionDeclarations
        if tools:
            body["tools"] = _openai_tools_to_gemini(tools)
            # tool_choice=="none" → disable function calling
            if tool_choice == "none":
                body["toolConfig"] = {
                    "functionCallingConfig": {"mode": "NONE"}
                }
            elif tool_choice == "auto" or tool_choice is None:
                body["toolConfig"] = {
                    "functionCallingConfig": {"mode": "AUTO"}
                }

        # Map OpenAI response_format JSON schema to Gemini response schema
        if response_format and response_format.get("type") == "json_schema":
            js = response_format.get("json_schema", {})
            schema = _strip_unsupported_schema_fields(js.get("schema", {}))
            body["generationConfig"] = {
                "responseMimeType": "application/json",
                "responseSchema": schema,
            }

        endpoint = f"models/{self._model}:generateContent"

        start_time = time.perf_counter()
        data = await self._post(endpoint, body)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return _extract_gemini_result(data, elapsed_ms)

