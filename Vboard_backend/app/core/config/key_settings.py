from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class KeySettings(BaseSettings):
    """Provider credentials and endpoint URLs.

    Secrets stay in .env and must never be logged or printed.
    """

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

    # Provider API keys (optional fallback / multi-provider support)
    SARVAM_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
