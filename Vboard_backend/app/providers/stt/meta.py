"""
app/providers/stt/meta.py

Meta Muse Voice Transcribe STT provider.

Implements the BaseSTTProvider protocol by wrapping the existing
Meta ASR multipart REST endpoint. All logic is migrated verbatim from
app/services/stt_service.py so the stt_service thin wrapper can delegate
to this class without any behaviour change.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

import httpx

from app.core.config import settings
from app.core.exceptions import InvalidAudioError, MetaApiError, RateLimitedError
from app.services.meta_client import get_meta_client
from app.services.stt_service import TranscriptionResult


class MetaSTTProvider:
    """
    STT provider backed by Meta Muse Voice Transcribe API.

    Uses the shared httpx.AsyncClient from meta_client.py.
    Retries once on HTTP 500 with a 300 ms delay.
    """

    async def transcribe(
        self,
        wav_bytes: bytes,
        languages: Optional[list[str]] = None,
    ) -> TranscriptionResult:
        """
        Transcribe WAV bytes using the Meta /asr/transcribe multipart endpoint.

        Args:
            wav_bytes: 16-bit PCM mono WAV bytes (16 or 24 kHz).
            languages: Optional language-bias hints (canonical Meta names).

        Returns:
            TranscriptionResult with transcript text and timing metrics.

        Raises:
            InvalidAudioError: HTTP 400 / 413 from Meta ASR.
            RateLimitedError: HTTP 429 from Meta ASR.
            MetaApiError: Network error or HTTP 500 (after one retry).
        """
        client = get_meta_client()
        endpoint = f"{str(client.base_url).rstrip('/')}/asr/transcribe"

        request_payload: dict = {
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
            # Retry once on HTTP 500 with a short delay
            if response.status_code == 500:
                await asyncio.sleep(0.3)
                response = await client.post(endpoint, files=files)
        except httpx.HTTPError as exc:
            raise MetaApiError(f"Meta API connection error: {exc}") from None

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if response.status_code == 200:
            try:
                data = response.json()
            except Exception:
                raise MetaApiError(
                    "Failed to parse Meta API response", status_code=200
                )
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

