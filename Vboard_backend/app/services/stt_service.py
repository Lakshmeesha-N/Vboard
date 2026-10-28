import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import InvalidAudioError, MetaApiError, RateLimitedError
from app.services.meta_client import get_meta_client


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
    Transcribe WAV audio bytes using the Meta Muse Voice Transcribe API.

    Args:
        wav_bytes: Audio bytes in 16-bit PCM mono WAV format (16 or 24 kHz).
        languages: Optional list of language bias hints (e.g. ["Kannada", "English"]).
                   If None or empty, "languageBias" is omitted from the request.

    Returns:
        TranscriptionResult containing transcript, elapsed ms, and audioDurationMs.

    Raises:
        InvalidAudioError: For HTTP 400 (bad audio) or 413 (payload too large).
        RateLimitedError: For HTTP 429 (rate limited).
        MetaApiError: For HTTP 500 (after 1 retry) and other unexpected API errors.
    """
    client = get_meta_client()
    endpoint = f"{str(client.base_url).rstrip('/')}/asr/transcribe"

    request_payload: dict[str, Any] = {
        "mode": "PUSH_TO_TALK",
        "model": settings.DEFAULT_VOICE_MODEL or "muse-voice-transcribe-1.0",
        "audioEncoding": "WAV",
    }
    if languages:
        request_payload["languageBias"] = list(languages)

    files = {
        "request": (None, json.dumps(request_payload), "application/json"),
        "audio": ("audio.wav", wav_bytes, "audio/wav"),
    }

    start_time = time.perf_counter()

    try:
        response = await client.post(endpoint, files=files)
        # Retry once on 500 only with a 0.3s delay
        if response.status_code == 500:
            await asyncio.sleep(0.3)
            response = await client.post(endpoint, files=files)
    except httpx.HTTPError:
        raise MetaApiError("Meta API connection error") from None

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    if response.status_code == 200:
        try:
            data = response.json()
        except Exception:
            raise MetaApiError("Failed to parse Meta API response", status_code=200)

        transcript = data.get("transcript", "")
        audio_duration_ms = data.get("audioDurationMs") or 0

        return TranscriptionResult(
            transcript=transcript,
            elapsed_ms=round(elapsed_ms, 2),
            audio_duration_ms=int(audio_duration_ms),
        )

    if response.status_code in (400, 413):
        raise InvalidAudioError("Invalid or unsupported audio payload")
    if response.status_code == 429:
        raise RateLimitedError("Meta API rate limit exceeded")
    if response.status_code == 500:
        raise MetaApiError("Meta API server error", status_code=500)

    raise MetaApiError(
        f"Meta API request failed with status {response.status_code}",
        status_code=response.status_code,
    )
