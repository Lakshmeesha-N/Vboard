"""
app/providers/llm/openai_compatible.py

OpenAI-compatible LLM provider.

Implements the BaseLLMProvider protocol using the openai Python SDK's
AsyncOpenAI client.  This single class powers three provider targets:

  - Meta Spark  (base_url=META_BASE_URL, model=muse-spark-1.3)
  - OpenAI      (base_url=None → sdk default, model=gpt-4o-mini)
  - Groq        (base_url=GROQ_BASE_URL, model=llama-3.3-70b-versatile)

The caller (factory.py) constructs the instance with the right parameters.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import openai
from loguru import logger

from app.core.exceptions import MetaApiError, RateLimitedError
from app.services.llm_client import get_llm_client
from app.services.llm_service import LLMResult, _extract_usage_field


class OpenAICompatibleLLMProvider:
    """
    LLM provider for any OpenAI-compatible chat-completion endpoint.

    Args:
        api_key: API key for the endpoint.
        model: Model identifier (e.g. "muse-spark-1.3", "gpt-4o-mini").
        base_url: Optional base URL override.  None uses the SDK default
                  (api.openai.com).
        timeout: Request timeout in seconds.
        max_retries: SDK-level retry count (network-layer only).
        use_shared_meta_client: Reuse the lifespan-managed Meta AsyncOpenAI
                                singleton when initialized.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        timeout: float = 20.0,
        max_retries: int = 1,
        use_shared_meta_client: bool = False,
    ) -> None:
        self._model = model
        self._use_shared_meta_client = use_shared_meta_client
        self._client_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        if base_url:
            self._client_kwargs["base_url"] = base_url

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    async def _create(self, **call_kwargs: Any) -> openai.types.chat.ChatCompletion:
        """Call chat.completions.create and normalise provider errors."""
        try:
            if self._use_shared_meta_client:
                try:
                    shared_client = get_llm_client()
                except RuntimeError:
                    shared_client = None
                if shared_client is not None:
                    return await shared_client.chat.completions.create(**call_kwargs)

            async with openai.AsyncOpenAI(**self._client_kwargs) as client:
                return await client.chat.completions.create(**call_kwargs)
        except openai.RateLimitError:
            raise RateLimitedError("Provider API rate limit exceeded") from None
        except (openai.APITimeoutError, openai.APIConnectionError):
            raise MetaApiError("Provider API connection error") from None
        except openai.APIStatusError as exc:
            raise MetaApiError(
                "Provider API request failed", status_code=exc.status_code
            ) from None
        except openai.OpenAIError:
            raise MetaApiError("Provider API request failed") from None

    @staticmethod
    def _build_result(response: Any, elapsed_ms: float) -> LLMResult:
        """Extract text and token metrics from a completion response."""
        text = ""

        choices = getattr(response, "choices", None)
        if choices and len(choices) > 0:
            first_choice = choices[0]
            message = getattr(first_choice, "message", None)
            if message is not None:
                text = getattr(message, "content", "") or ""
            elif isinstance(first_choice, dict):
                msg = first_choice.get("message", {})
                text = msg.get("content", "") or ""

        prompt_tokens = 0
        completion_tokens = 0
        cached_tokens = 0
        reasoning_tokens = 0

        usage = getattr(response, "usage", None)
        if usage is not None:
            prompt_tokens = _extract_usage_field(usage, "prompt_tokens")
            completion_tokens = _extract_usage_field(usage, "completion_tokens")

            prompt_details = (
                usage.get("prompt_tokens_details")
                if isinstance(usage, dict)
                else getattr(usage, "prompt_tokens_details", None)
            )
            cached_tokens = _extract_usage_field(prompt_details, "cached_tokens")

            completion_details = (
                usage.get("completion_tokens_details")
                if isinstance(usage, dict)
                else getattr(usage, "completion_tokens_details", None)
            )
            reasoning_tokens = _extract_usage_field(
                completion_details, "reasoning_tokens"
            )

        elapsed_rounded = round(elapsed_ms, 2)

        # Privacy: log numbers only
        logger.info(
            "LLM complete: elapsed_ms={:.2f}, prompt_tokens={}, "
            "completion_tokens={}, cached_tokens={}, reasoning_tokens={}",
            elapsed_rounded,
            prompt_tokens,
            completion_tokens,
            cached_tokens,
            reasoning_tokens,
        )

        return LLMResult(
            text=text,
            elapsed_ms=elapsed_rounded,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
        )

    # ------------------------------------------------------------------
    # BaseLLMProvider interface
    # ------------------------------------------------------------------

    async def complete(
        self,
        system_prompt: str,
        user_text: str,
        response_format: Optional[dict[str, Any]] = None,
        reasoning_effort: Optional[str] = None,
    ) -> LLMResult:
        """Single-turn system+user chat completion."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
        call_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if response_format is not None:
            call_kwargs["response_format"] = response_format
        if reasoning_effort is not None:
            call_kwargs["reasoning_effort"] = reasoning_effort

        start_time = time.perf_counter()
        response = await self._create(**call_kwargs)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return self._build_result(response, elapsed_ms)

