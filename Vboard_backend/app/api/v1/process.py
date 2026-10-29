import re
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from loguru import logger

from app.core.audio import META_SUPPORTED_LANGUAGES, validate_wav_bytes
from app.core.config import settings
from app.core.exceptions import InvalidAudioError, MetaApiError, RateLimitedError
from app.schemas.process import ProcessResponse
from app.services.stt_service import transcribe

router = APIRouter()

DEVICE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@router.post("/process", response_model=ProcessResponse)
async def process_audio(
    audio: UploadFile = File(..., description="16-bit PCM mono WAV audio file"),
    languages: Optional[str] = Form(
        None,
        description="Comma-separated language names (e.g. 'Kannada,English')",
    ),
    context_text: Optional[str] = Form(
        None,
        description="Optional screen context text (max 10,000 characters)",
    ),
    device_id: Optional[str] = Form(
        None,
        description="Optional client device identifier (max 64 alphanumeric chars)",
    ),
) -> ProcessResponse:
    """
    Process speech audio input with guardrail validation and transcribe with Meta STT.

    Enforces:
    - 5 MB maximum upload size via streaming read limit (HTTP 413).
    - Optional context_text length <= 10,000 chars (HTTP 400).
    - Strict privacy: context_text and audio bytes are NEVER logged.
    - Optional device_id matching [a-zA-Z0-9_-]{1,64} (HTTP 400).
    - Up to 5 languages validated against Meta's 25 supported languages (HTTP 400).
    - In-memory WAV audio validation (mono, 16-bit, 16/24kHz, 0.3-60s, non-silent).
    """
    # 1. Device ID validation & audit logging
    if device_id is not None:
        if not DEVICE_ID_PATTERN.match(device_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Invalid device_id: must be 1-64 alphanumeric "
                    "characters, underscores, or hyphens"
                ),
            )
        # Log ONLY the validated device identifier
        logger.info("Processing audio request for device: {}", device_id)

    # 2. Context text validation (strictly NEVER logged for user privacy)
    if (
        context_text is not None
        and len(context_text) > settings.MAX_CONTEXT_TEXT_LENGTH
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"context_text exceeds maximum limit of "
                f"{settings.MAX_CONTEXT_TEXT_LENGTH} characters"
            ),
        )

    # 3. Language bias parsing and whitelist validation
    parsed_languages: Optional[list[str]] = None
    if languages:
        raw_langs = [item.strip() for item in languages.split(",") if item.strip()]
        if len(raw_langs) > settings.MAX_LANGUAGES_COUNT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"languages cannot exceed {settings.MAX_LANGUAGES_COUNT} items",
            )
        for lang in raw_langs:
            if lang not in META_SUPPORTED_LANGUAGES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Unsupported language '{lang}'. "
                        "Must be one of the supported Meta languages."
                    ),
                )
        if raw_langs:
            parsed_languages = raw_langs

    # 4. Streaming read with early overflow termination (5 MB limit)
    wav_bytes = await audio.read(settings.MAX_AUDIO_BYTES + 1)
    if len(wav_bytes) > settings.MAX_AUDIO_BYTES:
        max_mb = settings.MAX_AUDIO_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Audio payload exceeds maximum size limit of {max_mb} MB",
        )
    if not wav_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio payload is empty",
        )

    # 5. In-memory Audio Guardrail validation
    try:
        validate_wav_bytes(wav_bytes)
    except InvalidAudioError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    # 6. Dispatch transcription to Meta STT service
    try:
        result = await transcribe(wav_bytes, languages=parsed_languages)
    except InvalidAudioError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RateLimitedError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except MetaApiError as exc:
        status_code = (
            status.HTTP_500_INTERNAL_SERVER_ERROR
            if exc.status_code == 500
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return ProcessResponse(
        transcript=result.transcript,
        timing_ms=result.elapsed_ms,
        audio_duration_ms=result.audio_duration_ms,
    )