from pydantic import Field
from pydantic_settings import BaseSettings


class StreamingSettings(BaseSettings):
    """Streaming endpoint limits (new STREAM_* settings, nothing reads them yet)."""

    STREAM_MAX_SECONDS: float = Field(
        default=60.0,
        description="Maximum streaming recording length in seconds",
    )
    STREAM_IDLE_TIMEOUT_S: float = Field(
        default=15.0,
        description="Close the stream after this many seconds without audio",
    )
    STREAM_MAX_BYTES: int = Field(
        default=5 * 1024 * 1024,
        description="Maximum cumulative streaming audio bytes (5 MB)",
    )
    STREAM_CHUNK_MS: int = Field(
        default=100,
        description="Expected audio chunk length in milliseconds",
    )
