import time
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from loguru import logger

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
    read_start = time.perf_counter()
    wav_bytes = await audio.read(settings.MAX_AUDIO_BYTES + 1)
    read_ms = (time.perf_counter() - read_start) * 1000.0

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

    result = await pipeline.run(
        wav_bytes,
        languages=parsed_langs,
        read_ms=read_ms,
    )

    # Always log timing numbers with device_id (numbers only, never audio/text)
    t = result.timings_ms
    logger.info(
        "Timings for device {}: read_ms={:.2f}, guardrail_ms={:.2f}, "
        "stt_ms={:.2f}, total_ms={:.2f}",
        device_id or "none",
        t.get("read_ms", 0.0),
        t.get("guardrail_ms", 0.0),
        t.get("stt_ms", 0.0),
        t.get("total_ms", 0.0),
    )

    # Include timings_ms in response only when DEBUG is enabled
    response_timings = result.timings_ms if settings.DEBUG else None

    return ProcessResponse(
        transcript=result.transcript,
        timing_ms=result.timings_ms["total_ms"],
        audio_duration_ms=result.audio_duration_ms,
        timings_ms=response_timings,
    )
