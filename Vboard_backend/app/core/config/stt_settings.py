from pydantic import Field
from pydantic_settings import BaseSettings


class SttSettings(BaseSettings):
    """STT provider selection and voice model defaults."""

    # Voice / Audio model defaults
    DEFAULT_VOICE_MODEL: str = Field(
        default="muse-voice-transcribe-1.0",
        description="Default voice/ASR model identifier",
    )

    # Provider selection switch (default to "meta" for backward compatibility)
    STT_PROVIDER: str = Field(
        default="meta",
        description="Active STT provider: meta, sarvam, openai",
    )

    # Per-provider model overrides
    OPENAI_VOICE_MODEL: str = Field(
        default="whisper-1",
        description="OpenAI STT model identifier",
    )
    SARVAM_VOICE_MODEL: str = Field(
        default="saaras:v2",
        description="Sarvam ASR model identifier",
    )
    SARVAM_BASE_URL: str = Field(
        default="https://api.sarvam.ai",
        description="Base URL for the Sarvam AI API",
    )
