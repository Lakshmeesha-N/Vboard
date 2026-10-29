from typing import Optional

from pydantic import BaseModel, Field


class ProcessResponse(BaseModel):
    """Transcription response returned by POST /v1/process."""

    transcript: str = Field(..., description="Transcribed text output")
    timing_ms: float = Field(..., description="Processing time in milliseconds")
    audio_duration_ms: int = Field(
        ..., description="Duration of processed audio in milliseconds"
    )
    timings_ms: Optional[dict[str, float]] = Field(
        default=None,
        description="Per-stage server timings in milliseconds (debug mode only)",
    )
