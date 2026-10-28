import httpx
import pytest
from app.main import app, lifespan
from app.services.meta_client import get_meta_client


@pytest.mark.asyncio
async def test_meta_client_lifecycle():
    # Before startup, client is uninitialized
    with pytest.raises(RuntimeError):
        get_meta_client()

    # Enter lifespan (startup)
    async with lifespan(app):
        client = get_meta_client()
        assert isinstance(client, httpx.AsyncClient)
        assert not client.is_closed
        assert client.timeout.connect == 5.0
        assert client.timeout.read == 30.0

    # After lifespan (shutdown)
    assert client.is_closed
    with pytest.raises(RuntimeError):
        get_meta_client()
