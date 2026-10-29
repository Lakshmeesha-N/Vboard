from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root directory: Vboard_backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    """

    # Application settings
    APP_NAME: str = "Vboard Backend"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Meta / Llama API configuration
    META_API_KEY: Optional[str] = Field(
        default=None,
        description="API key for Meta/Llama API services",
    )
    META_BASE_URL: Optional[str] = Field(
        default="https://api.meta.ai/v1",
        description="Base URL for Meta API endpoints",
    )

    # Hugging Face configuration
    HF_TOKEN: Optional[str] = Field(
        default=None,
        description="Hugging Face API token",
    )

    # Voice / Audio model defaults
    DEFAULT_VOICE_MODEL: str = Field(
        default="muse-voice-transcribe-1.0",
        description="Default voice/ASR model identifier",
    )

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
        default=50.0,
        description="RMS amplitude threshold below which audio is treated as silent",
    )

    # Request validation settings
    MAX_CONTEXT_TEXT_LENGTH: int = Field(
        default=10000,
        description="Maximum length of context_text string in characters",
    )
    MAX_LANGUAGES_COUNT: int = Field(
        default=5,
        description="Maximum number of languages allowed in languageBias",
    )

    # LLM model defaults
    DEFAULT_LLM_MODEL: str = Field(
        default="meta-llama/Meta-Llama-3.1-8B-Instruct",
        description="Default LLM model identifier",
    )

    # Provider API keys (optional fallback / multi-provider support)
    SARVAM_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        # Look for .env in Vboard_backend directory first, then the workspace root
        env_file=(BASE_DIR / ".env", BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Single global config instance
settings = Settings()
config = settings
