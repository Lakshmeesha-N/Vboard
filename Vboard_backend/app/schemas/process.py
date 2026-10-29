from typing import Optional

from pydantic import BaseModel, Field


class ActionModel(BaseModel):
    """Editing action structure matching client keyboard requirements."""

    action: str = Field(..., description="Action type: insert, replace, or rewrite")
    text: str = Field(..., description="Text content for the action")
    find: Optional[str] = Field(
        default=None, description="Target text to find and replace"
    )
    which: Optional[str] = Field(
        default=None, description="Target occurrence indicator, if any"
    )


class ProcessResponse(BaseModel):
    """Transcription and action response returned by POST /v1/process."""

    transcript: str = Field(..., description="Transcribed text output")
    timing_ms: float = Field(..., description="Processing time in milliseconds")
    audio_duration_ms: int = Field(
        ..., description="Duration of processed audio in milliseconds"
    )
    action: Optional[ActionModel] = Field(
        default=None, description="Determined editing action or null"
    )
    used_fallback: bool = Field(
        default=False, description="Whether fallback action was used"
    )
    note: Optional[str] = Field(
        default=None, description="Fallback reason code, if applicable"
    )
    timings_ms: Optional[dict[str, float]] = Field(
        default=None,
        description="Per-stage server timings in milliseconds (debug mode only)",
    )
