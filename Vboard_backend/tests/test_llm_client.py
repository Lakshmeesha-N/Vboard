import pytest
from openai import AsyncOpenAI

from app.main import app, lifespan
from app.services.llm_client import (
    close_llm_client,
    get_llm_client,
    init_llm_client,
)


@pytest.mark.asyncio
async def test_llm_client_lifecycle():
    # Ensure client is cleared before test
    await close_llm_client()

    # Before startup, client is uninitialized
    with pytest.raises(RuntimeError) as exc_info:
        get_llm_client()
    assert "LLM client is not initialized or has been closed" in str(exc_info.value)

    # Enter lifespan (startup)
    async with lifespan(app):
        client = get_llm_client()
        assert isinstance(client, AsyncOpenAI)
        assert not client.is_closed()
        assert client.timeout == 20.0
        assert client.max_retries == 1

        # Idempotent init: calling init again returns the same client instance
        same_client = await init_llm_client()
        assert same_client is client

    # After lifespan (shutdown)
    assert client.is_closed()
    with pytest.raises(RuntimeError):
        get_llm_client()
