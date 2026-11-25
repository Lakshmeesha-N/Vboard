from pydantic import Field
from pydantic_settings import BaseSettings


class AudioSettings(BaseSettings):
    """Audio guardrail limits."""

    # Audio Guardrail settings
    MAX_AUDIO_BYTES: int = Field(
        default=5 * 1024 * 1024,
        description="Maximum allowed audio upload size in bytes (5 MB)",
    )
    MIN_AUDIO_DURATION_S: float = Field(
        default=0.3,
        description="Minimum allowed audio duration in seconds",
    )
    MAX_AUDIO_DURATION_S: float = Field(
        default=60.0,
        description="Maximum allowed audio duration in seconds",
    )
    SILENCE_RMS_THRESHOLD: float = Field(
        default=20.0,
        description="RMS amplitude threshold below which audio is treated as silent",
    )
