from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class LlmSettings(BaseSettings):
    """LLM provider selection and model defaults."""

    # LLM model defaults
    DEFAULT_LLM_MODEL: str = Field(
        default="muse-spark-1.3",
        description="Default LLM model identifier",
    )
    SPARK_REASONING_EFFORT: str = Field(
        default="minimal",
        description="Reasoning effort level for Spark Chat Completions",
    )

    # Provider selection switch (default to "meta" for backward compatibility)
    LLM_PROVIDER: str = Field(
        default="meta",
        description="Active LLM provider: meta, openai, groq, google",
    )

    # Per-provider model overrides
    OPENAI_LLM_MODEL: str = Field(
        default="gpt-4o-mini",
        description="OpenAI chat completion model identifier",
    )
    GEMINI_LLM_MODEL: str = Field(
        default="gemini-2.5-flash",
        description="Google Gemini chat completion model identifier",
    )
    GROQ_LLM_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq chat completion model identifier",
    )
    GROQ_BASE_URL: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Base URL for the Groq OpenAI-compatible API",
    )
    OPENAI_BASE_URL: Optional[str] = None
