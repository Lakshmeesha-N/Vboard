"""
app/providers/base.py

Protocol interfaces for the STT and LLM provider abstraction layer.
All provider implementations must satisfy these contracts so that
stt_service.py and llm_service.py can delegate to any provider without
knowing its concrete type.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Forward-declared result types (re-exported from their source modules so
# providers can import them without circular dependency).
# ---------------------------------------------------------------------------

# TranscriptionResult is defined in stt_service; re-import at usage sites.
# LLMResult is defined in llm_service; re-import at usage sites.


@runtime_checkable
class BaseSTTProvider(Protocol):
    """
    Contract for speech-to-text providers.

    Implementations must accept WAV bytes and an optional language-hint list
    and must return a TranscriptionResult-compatible dataclass.
    """

    async def transcribe(
        self,
        wav_bytes: bytes,
        languages: Optional[list[str]] = None,
    ) -> Any:
        """
        Transcribe PCM WAV bytes.

        Args:
            wav_bytes: 16-bit PCM mono WAV bytes (16 or 24 kHz).
            languages: Optional list of language-bias hints
                       (canonical names like ["Kannada", "English"]).

        Returns:
            TranscriptionResult(transcript, elapsed_ms, audio_duration_ms).

        Raises:
            InvalidAudioError: If the payload is rejected by the provider.
            RateLimitedError: On HTTP 429 / quota exhausted.
            MetaApiError: On provider 5xx / network errors.
        """
        ...


@runtime_checkable
class BaseLLMProvider(Protocol):
    """
    Contract for large-language-model providers.

    Implementations must expose two entry points:
      - complete(): simple system+user prompt → text
      - complete_messages(): full message history with optional tools →
        text + tool_calls
    Both must return an LLMResult-compatible dataclass.
    """

    async def complete(
        self,
        system_prompt: str,
        user_text: str,
        response_format: Optional[dict[str, Any]] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Any:
        """
        Single-turn chat completion.

        Args:
            system_prompt: System directive.
            user_text: User message.
            response_format: Optional structured JSON schema constraint.
            reasoning_effort: Optional effort hint (e.g. "minimal").

        Returns:
            LLMResult(text, elapsed_ms, prompt_tokens, completion_tokens,
                      cached_tokens, reasoning_tokens, tool_calls=[]).

        Raises:
            RateLimitedError: On HTTP 429.
            MetaApiError: On timeout, connection error, or other 5xx.
        """
        ...

    async def complete_messages(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        response_format: Optional[dict[str, Any]] = None,
        reasoning_effort: Optional[str] = None,
    ) -> Any:
        """
        Multi-turn chat completion with optional function/tool support.

        Args:
            messages: Full message history (system/user/assistant/tool roles).
            tools: Optional list of tool definitions.
            tool_choice: Optional tool choice constraint.
            response_format: Optional structured JSON schema constraint.
            reasoning_effort: Optional effort hint.

        Returns:
            LLMResult with text, tool_calls, and token metrics.

        Raises:
            RateLimitedError: On HTTP 429.
            MetaApiError: On timeout, connection error, or other 5xx.
        """
        ...

