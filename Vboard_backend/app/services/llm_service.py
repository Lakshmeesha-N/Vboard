from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class LLMResult:
    """Dataclass holding LLM generation output and token consumption metrics."""

    text: str
    elapsed_ms: float
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    reasoning_tokens: int
    tool_calls: list[Any] = field(default_factory=list)


def _extract_usage_field(obj: Any, field_name: str) -> int:
    """Extract an integer field from an object or dictionary, defaulting to 0."""
    if obj is None:
        return 0
    if isinstance(obj, dict):
        val = obj.get(field_name, 0)
    else:
        val = getattr(obj, field_name, 0)
    return int(val) if val is not None else 0


async def complete(
    system_prompt: str,
    user_text: str,
    response_format: Optional[dict[str, Any]] = None,
    reasoning_effort: Optional[str] = None,
) -> LLMResult:
    """
    Execute a chat completion using the active LLM provider.

    The provider is selected by settings.LLM_PROVIDER (default: "meta").
    See app/providers/factory.py for available providers.

    Args:
        system_prompt: System directive instructions.
        user_text: User message input.
        response_format: Optional structured output format constraint.
        reasoning_effort: Optional reasoning effort level.

    Returns:
        LLMResult containing response text, elapsed milliseconds, and token metrics.

    Raises:
        RateLimitedError: When HTTP 429 rate limit is encountered.
        MetaApiError: On timeouts, connection errors, or other upstream API failures.
    """
    from app.providers.factory import get_llm_provider

    provider = get_llm_provider()
    return await provider.complete(
        system_prompt,
        user_text,
        response_format=response_format,
        reasoning_effort=reasoning_effort,
    )


async def complete_messages(
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: Optional[Any] = None,
    response_format: Optional[dict[str, Any]] = None,
    reasoning_effort: Optional[str] = None,
) -> LLMResult:
    """
    Execute a chat completion call with full message history and tool support.

    The provider is selected by settings.LLM_PROVIDER (default: "meta").
    See app/providers/factory.py for available providers.

    Args:
        messages: Full conversation history (system/user/assistant/tool).
        tools: Optional list of tool definitions (e.g. web_search).
        tool_choice: Optional tool choice constraint ("auto", "none", ...).
        response_format: Optional structured output format constraint.
        reasoning_effort: Optional reasoning effort level.

    Returns:
        LLMResult with response text, tool calls, and token metrics.
    """
    from app.providers.factory import get_llm_provider

    provider = get_llm_provider()
    return await provider.complete_messages(
        messages,
        tools=tools,
        tool_choice=tool_choice,
        response_format=response_format,
        reasoning_effort=reasoning_effort,
    )
