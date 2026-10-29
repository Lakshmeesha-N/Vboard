import time
from dataclasses import dataclass
from typing import Any

import openai
from loguru import logger

from app.core.config import settings
from app.core.exceptions import MetaApiError, RateLimitedError
from app.services.llm_client import get_llm_client


@dataclass(frozen=True)
class LLMResult:
    """Dataclass holding LLM generation output and token consumption metrics."""

    text: str
    elapsed_ms: float
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    reasoning_tokens: int


def _extract_usage_field(obj: Any, field_name: str) -> int:
    """Extract an integer field from an object or dictionary, defaulting to 0."""
    if obj is None:
        return 0
    if isinstance(obj, dict):
        val = obj.get(field_name, 0)
    else:
        val = getattr(obj, field_name, 0)
    return int(val) if val is not None else 0


async def complete(system_prompt: str, user_text: str) -> LLMResult:
    """
    Execute a chat completion call using the shared Meta LLM client.

    Args:
        system_prompt: System directive instructions.
        user_text: User message input.

    Returns:
        LLMResult containing response text, elapsed milliseconds, and token metrics.

    Raises:
        RateLimitedError: When HTTP 429 rate limit is encountered.
        MetaApiError: On timeouts, connection errors, or other upstream API failures.
    """
    client = get_llm_client()
    model = settings.DEFAULT_LLM_MODEL or "muse-spark-1.3"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    start_time = time.perf_counter()

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
        )
    except openai.RateLimitError:
        raise RateLimitedError("Meta API rate limit exceeded") from None
    except (openai.APITimeoutError, openai.APIConnectionError):
        raise MetaApiError("Meta API connection error") from None
    except openai.APIStatusError as exc:
        raise MetaApiError(
            "Meta API request failed", status_code=exc.status_code
        ) from None
    except openai.OpenAIError:
        raise MetaApiError("Meta API request failed") from None

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Extract text content safely
    text = ""
    choices = getattr(response, "choices", None)
    if choices and len(choices) > 0:
        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        if message is not None:
            text = getattr(message, "content", "") or ""
        elif isinstance(first_choice, dict):
            text = first_choice.get("message", {}).get("content", "") or ""

    # Extract usage metrics with safe 0 fallbacks
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
        reasoning_tokens = _extract_usage_field(completion_details, "reasoning_tokens")

    elapsed_ms_rounded = round(elapsed_ms, 2)

    # Privacy requirement: Log numbers only, never user text/prompts
    logger.info(
        "LLM complete: elapsed_ms={:.2f}, prompt_tokens={}, "
        "completion_tokens={}, cached_tokens={}, reasoning_tokens={}",
        elapsed_ms_rounded,
        prompt_tokens,
        completion_tokens,
        cached_tokens,
        reasoning_tokens,
    )

    return LLMResult(
        text=text,
        elapsed_ms=elapsed_ms_rounded,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        reasoning_tokens=reasoning_tokens,
    )
