from typing import Optional
import httpx
from app.core.config import settings

_client: Optional[httpx.AsyncClient] = None


async def init_meta_client() -> httpx.AsyncClient:
    """Initialize the shared httpx.AsyncClient for Meta API calls."""
    global _client
    if _client is not None and not _client.is_closed:
        return _client

    headers = {}
    if settings.META_API_KEY:
        headers["Authorization"] = f"Bearer {settings.META_API_KEY}"

    base_url = settings.META_BASE_URL or "https://api.meta.ai/v1"
    timeout = httpx.Timeout(30.0, connect=5.0)

    _client = httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=timeout,
    )
    return _client


async def close_meta_client() -> None:
    """Close the shared httpx.AsyncClient on app shutdown."""
    global _client
    if _client is not None:
        if not _client.is_closed:
            await _client.aclose()
        _client = None


def get_meta_client() -> httpx.AsyncClient:
    """Get the shared httpx.AsyncClient instance."""
    if _client is None or _client.is_closed:
        raise RuntimeError("Meta client is not initialized or has been closed")
    return _client
