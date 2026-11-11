"""
app/providers/stt/sarvam.py

Sarvam AI (Saaras) STT provider.

Implements the BaseSTTProvider protocol by calling the Sarvam
speech-to-text REST endpoint, which excels at Indian-language audio.
Requires settings.SARVAM_API_KEY to be set.
"""

from __future__ import annotations

import time
from typing import Optional

import httpx

from app.core.config import settings
from app.core.exceptions import InvalidAudioError, MetaApiError, RateLimitedError
from app.services.stt_service import TranscriptionResult

# Mapping from canonical Meta language names to Sarvam BCP-47 codes.
# Only the 25 languages validated by app/core/validators.py are listed;
# unmapped languages are dropped rather than sent as-is.
_LANG_TO_BCP47: dict[str, str] = {
    "English": "en-IN",
    "Hindi": "hi-IN",
    "Bengali": "bn-IN",
    "Kannada": "kn-IN",
    "Malayalam": "ml-IN",
    "Marathi": "mr-IN",
    "Tamil": "ta-IN",
    "Telugu": "te-IN",
    "Gujarati": "gu-IN",
    "Odia": "od-IN",
    "Punjabi": "pa-IN",
    "Assamese": "as-IN",
    "Rajasthani": "raj-IN",
    "Sanskrit": "sa-IN",
    "Urdu": "ur-IN",
}


class SarvamSTTProvider:
    """
    STT provider backed by Sarvam AI Saaras speech-to-text API.

    Sends WAV bytes as multipart/form-data to the Sarvam ASR endpoint.
    Maps the first canonical language hint to a BCP-47 code when provided.
    Does NOT retry on 500 (Sarvam SLA is different from Meta's).
    """

    async def transcribe(
        self,
        wav_bytes: bytes,
        languages: Optional[list[str]] = None,
    ) -> TranscriptionResult:
        """
        Transcribe WAV bytes using the Sarvam speech-to-text API.

        Args:
            wav_bytes: 16-bit PCM mono WAV bytes.
            languages: Optional language-bias hints (canonical Meta names).
                       The first mappable language is used as language_code.

        Returns:
            TranscriptionResult with transcript text and timing metrics.

        Raises:
            InvalidAudioError: HTTP 400 / 413 from Sarvam.
            RateLimitedError: HTTP 429 from Sarvam.
            MetaApiError: Network error or HTTP 500.
        """
        api_key = settings.SARVAM_API_KEY or ""
        base_url = settings.SARVAM_BASE_URL.rstrip("/")
        model = settings.SARVAM_VOICE_MODEL

        headers = {"api-subscription-key": api_key}

        # Pick the first language that maps to a BCP-47 code
        language_code: Optional[str] = None
        if languages:
            for lang in languages:
                code = _LANG_TO_BCP47.get(lang)
                if code:
                    language_code = code
                    break

        data: dict = {"model": model}
        if language_code:
            data["language_code"] = language_code

        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}

        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(30.0, connect=5.0),
            ) as client:
                response = await client.post(
                    f"{base_url}/speech-to-text",
                    data=data,
                    files=files,
                )
        except httpx.HTTPError as exc:
            raise MetaApiError(f"Sarvam API connection error: {exc}") from None

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if response.status_code == 200:
            try:
                payload = response.json()
            except Exception:
                raise MetaApiError(
                    "Failed to parse Sarvam API response", status_code=200
                )
            transcript = payload.get("transcript", "")
            # Sarvam does not return audio duration; default to 0
            return TranscriptionResult(
                transcript=transcript,
                elapsed_ms=round(elapsed_ms, 2),
                audio_duration_ms=0,
            )

        if response.status_code in (400, 413):
            raise InvalidAudioError("Invalid or unsupported audio payload")
        if response.status_code == 429:
            raise RateLimitedError("Sarvam API rate limit exceeded")
        if response.status_code == 500:
            raise MetaApiError("Sarvam API server error", status_code=500)

        raise MetaApiError(
            f"Sarvam API request failed with status {response.status_code}",
            status_code=response.status_code,
        )

