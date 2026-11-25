from pydantic import Field
from pydantic_settings import BaseSettings


class ValidationSettings(BaseSettings):
    """Request validation limits."""

    # Request validation settings
    MAX_CONTEXT_TEXT_LENGTH: int = Field(
        default=10000,
        description="Maximum length of context_text string in characters",
    )
    MAX_LANGUAGES_COUNT: int = Field(
        default=5,
        description="Maximum number of languages allowed in languageBias",
    )
