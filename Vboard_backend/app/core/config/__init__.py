from pathlib import Path

from pydantic_settings import SettingsConfigDict

from app.core.config.app_settings import AppSettings
from app.core.config.audio_settings import AudioSettings
from app.core.config.key_settings import KeySettings
from app.core.config.llm_settings import LlmSettings
from app.core.config.streaming_settings import StreamingSettings
from app.core.config.stt_settings import SttSettings
from app.core.config.validation_settings import ValidationSettings

# Project root directory: Vboard_backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(
    AppSettings,
    LlmSettings,
    SttSettings,
    AudioSettings,
    ValidationSettings,
    KeySettings,
    StreamingSettings,
):
    """
    Application settings loaded from environment variables and .env file.

    Single combined object; field names and defaults match the old
    app/core/config.py. Secrets stay in .env and must never be logged.
    """

    model_config = SettingsConfigDict(
        # Look for .env in Vboard_backend directory first, then the workspace root
        env_file=(BASE_DIR / ".env", BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Single global config instance
settings = Settings()
config = settings
