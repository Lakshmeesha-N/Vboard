from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TranscriptionResult:
    """Transcription output and performance metrics."""

    transcript: str
    elapsed_ms: float
    audio_duration_ms: int


async def transcribe(
    wav_bytes: bytes,
    languages: Optional[list[str]] = None,
) -> TranscriptionResult:
    """
    Transcribe WAV audio bytes using the active STT provider.

    The provider is selected by settings.STT_PROVIDER (default: "meta").
    See app/providers/factory.py for available providers.

    Args:
        wav_bytes: Audio bytes in 16-bit PCM mono WAV format (16 or 24 kHz).
        languages: Optional list of language bias hints (e.g. ["Kannada", "English"]).

    Returns:
        TranscriptionResult containing transcript, elapsed ms, and audioDurationMs.

    Raises:
        InvalidAudioError: For invalid or oversized audio payload.
        RateLimitedError: For HTTP 429 (rate limited).
        MetaApiError: For provider 5xx / network errors.
    """
    from app.providers.factory import get_stt_provider

    provider = get_stt_provider()
    return await provider.transcribe(wav_bytes, languages=languages)
