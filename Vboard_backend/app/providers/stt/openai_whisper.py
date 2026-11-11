"""
app/providers/stt/openai_whisper.py

OpenAI Whisper STT provider.

Implements the BaseSTTProvider protocol by calling OpenAI's
audio transcription endpoint (/v1/audio/transcriptions) using the
openai Python SDK. Requires settings.OPENAI_API_KEY to be set.
"""

from __future__ import annotations

import io
import time
from typing import Optional

import openai

from app.core.config import settings
from app.core.exceptions import InvalidAudioError, MetaApiError, RateLimitedError
from app.services.stt_service import TranscriptionResult

# Mapping from canonical Meta language names to ISO-639-1 codes accepted
# by OpenAI Whisper. Unmapped languages are omitted (Whisper auto-detects).
_LANG_TO_ISO639: dict[str, str] = {
    "English": "en",
    "Hindi": "hi",
    "Bengali": "bn",
    "Kannada": "kn",
    "Malayalam": "ml",
    "Marathi": "mr",
    "Tamil": "ta",
    "Telugu": "te",
    "Gujarati": "gu",
    "Punjabi": "pa",
    "Urdu": "ur",
    "Sanskrit": "sa",
    "Assamese": "as",
    "Odia": "or",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Portuguese": "pt",
    "Italian": "it",
    "Arabic": "ar",
    "Chinese": "zh",
    "Japanese": "ja",
    "Korean": "ko",
    "Russian": "ru",
    "Indonesian": "id",
}


class OpenAIWhisperSTTProvider:
    """
    STT provider backed by OpenAI Whisper (audio transcriptions endpoint).

    Creates a fresh AsyncOpenAI client on each call to avoid shared-client
    lifecycle coupling.  API key and optional base URL are read from settings.
    """

    async def transcribe(
        self,
        wav_bytes: bytes,
        languages: Optional[list[str]] = None,
    ) -> TranscriptionResult:
        """
        Transcribe WAV bytes using the OpenAI Whisper API.

        Args:
            wav_bytes: 16-bit PCM mono WAV bytes.
            languages: Optional language-bias hints (canonical Meta names).
                       The first mappable language is passed to Whisper.

        Returns:
            TranscriptionResult with transcript text and timing metrics.

        Raises:
            InvalidAudioError: HTTP 400 / 413 from OpenAI.
            RateLimitedError: HTTP 429 from OpenAI.
            MetaApiError: Network error or HTTP 500.
        """
        api_key = settings.OPENAI_API_KEY or "none"
        base_url = settings.OPENAI_BASE_URL or None
        model = settings.OPENAI_VOICE_MODEL

        # Pick the first language that maps to an ISO-639-1 code
        language: Optional[str] = None
        if languages:
            for lang in languages:
                code = _LANG_TO_ISO639.get(lang)
                if code:
                    language = code
                    break

        client_kwargs: dict = {"api_key": api_key, "timeout": 30.0, "max_retries": 1}
        if base_url:
            client_kwargs["base_url"] = base_url

        start_time = time.perf_counter()

        try:
            async with openai.AsyncOpenAI(**client_kwargs) as client:
                audio_file = io.BytesIO(wav_bytes)
                audio_file.name = "audio.wav"
                call_kwargs: dict = {"model": model, "file": audio_file}
                if language:
                    call_kwargs["language"] = language
                transcription = await client.audio.transcriptions.create(
                    **call_kwargs
                )
        except openai.RateLimitError:
            raise RateLimitedError("OpenAI API rate limit exceeded") from None
        except (openai.APITimeoutError, openai.APIConnectionError):
            raise MetaApiError("OpenAI API connection error") from None
        except openai.BadRequestError:
            raise InvalidAudioError("Invalid or unsupported audio payload")
        except openai.APIStatusError as exc:
            raise MetaApiError(
                "OpenAI API request failed", status_code=exc.status_code
            ) from None
        except openai.OpenAIError:
            raise MetaApiError("OpenAI API request failed") from None

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return TranscriptionResult(
            transcript=transcription.text or "",
            elapsed_ms=round(elapsed_ms, 2),
            audio_duration_ms=0,  # Whisper API does not return duration
        )

