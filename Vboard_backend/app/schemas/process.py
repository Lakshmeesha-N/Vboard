from pydantic import BaseModel, Field


class ProcessResponse(BaseModel):
    """Transcription response returned by POST /v1/process."""

    transcript: str = Field(..., description="Transcribed text output")
    timing_ms: float = Field(..., description="Processing time in milliseconds")
    audio_duration_ms: int = Field(
        ..., description="Duration of processed audio in milliseconds"
    )

