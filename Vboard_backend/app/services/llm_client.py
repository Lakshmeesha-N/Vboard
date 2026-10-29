from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings

_client: Optional[AsyncOpenAI] = None


async def init_llm_client() -> AsyncOpenAI:
    """Initialize the shared AsyncOpenAI client."""
    global _client
    if _client is not None and not _client.is_closed():
        return _client

    api_key = settings.META_API_KEY or "none"
    base_url = settings.META_BASE_URL or "https://api.meta.ai/v1"

    _client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=20.0,
        max_retries=1,
    )
    return _client


async def close_llm_client() -> None:
    """Close the shared AsyncOpenAI client on app shutdown."""
    global _client
    if _client is not None:
        if not _client.is_closed():
            await _client.close()
        _client = None


def get_llm_client() -> AsyncOpenAI:
    """Get the shared AsyncOpenAI client instance."""
    if _client is None or _client.is_closed():
        raise RuntimeError("LLM client is not initialized or has been closed")
    return _client
