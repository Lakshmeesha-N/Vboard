"""
app/providers/llm/gemini.py

Google Gemini LLM provider.

Implements the BaseLLMProvider protocol using the Google GenAI REST API
via httpx.  This avoids adding the google-genai SDK as a mandatory
dependency while keeping the provider fully functional.

Requires settings.GEMINI_API_KEY to be set.

Structured output (response_format) is mapped to Gemini's
response_mime_type + response_schema when the format is a JSON schema.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx
from loguru import logger

from app.core.exceptions import MetaApiError, RateLimitedError
from app.services.llm_service import LLMResult

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


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


def _extract_gemini_result(
    data: dict[str, Any], elapsed_ms: float
) -> LLMResult:
    """Parse a Gemini generateContent response dict into an LLMResult."""
    text = ""

    candidates = data.get("candidates", [])
    if candidates:
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        for part in parts:
            if "text" in part:
                text += part["text"]

    usage = data.get("usageMetadata", {})
    prompt_tokens = int(usage.get("promptTokenCount", 0))
    completion_tokens = int(usage.get("candidatesTokenCount", 0))

    elapsed_rounded = round(elapsed_ms, 2)

    logger.info(
        "LLM complete (gemini): elapsed_ms={:.2f}, prompt_tokens={}, "
        "completion_tokens={}",
        elapsed_rounded,
        prompt_tokens,
        completion_tokens,
    )

    return LLMResult(
        text=text,
        elapsed_ms=elapsed_rounded,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=0,
        reasoning_tokens=0,
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
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": user_text}]}]
        }

        if system_prompt:
            body["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
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

