from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.validators import (
    parse_languages,
    validate_context_text,
    validate_device_id,
)
from app.schemas.process import ProcessResponse
from app.services import pipeline

router = APIRouter()


@router.post("/process", response_model=ProcessResponse)
async def process_audio(
    audio: UploadFile = File(..., description="16-bit PCM mono WAV audio file"),
    languages: Optional[str] = Form(None),
    context_text: Optional[str] = Form(None),
    device_id: Optional[str] = Form(None),
) -> ProcessResponse:
    """Thin HTTP endpoint for speech processing."""
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

    validate_device_id(device_id)
    validate_context_text(context_text)
    parsed_langs = parse_languages(languages)

    result = await pipeline.run(wav_bytes, languages=parsed_langs)

    return ProcessResponse(
        transcript=result.transcript,
        timing_ms=result.timings_ms["total_ms"],
        audio_duration_ms=result.audio_duration_ms,
    )
