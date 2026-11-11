from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.exceptions import RateLimitedError
from app.main import app
from app.services.llm_service import LLMResult


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_cleanup_default():
    """Normal text routes to cleanup, returns corrected text."""
    mock_result = LLMResult(
        text="I went to the market yesterday and bought some vegetables.",
        elapsed_ms=45.2,
        prompt_tokens=25,
        completion_tokens=15,
        cached_tokens=0,
        reasoning_tokens=0,
    )
    with patch(
        "app.services.llm_service.complete",
        new=AsyncMock(return_value=mock_result),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/agent",
                json={
                    "content": "i went to market yestraday and buyed some vegitables"
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert (
                data["text"]
                == "I went to the market yesterday and bought some vegetables."
            )
            assert data["timing_ms"] == 45.2


@pytest.mark.asyncio
async def test_cleanup_translate():
    """Text containing translation instruction correctly translates and cleans."""
    mock_result = LLMResult(
        text="I am going home today.",
        elapsed_ms=52.1,
        prompt_tokens=20,
        completion_tokens=8,
        cached_tokens=0,
        reasoning_tokens=0,
    )
    with patch(
        "app.services.llm_service.complete",
        new=AsyncMock(return_value=mock_result),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/agent",
                json={
                    "content": "translate to English\nnaanu ivattu manege hoguttene",
                    "languages": "Kannada,English",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["text"] == "I am going home today."


@pytest.mark.asyncio
async def test_at_agent_prefix_treated_as_normal_cleanup():
    """Text starting with @agent is treated as normal text and cleaned up."""
    mock_result = LLMResult(
        text="@agent, please fix my grammar.",
        elapsed_ms=12.3,
        prompt_tokens=10,
        completion_tokens=7,
        cached_tokens=0,
        reasoning_tokens=0,
    )
    with patch(
        "app.services.llm_service.complete",
        new=AsyncMock(return_value=mock_result),
    ) as mock_complete:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/agent",
                json={"content": "@agent pls fix my grammer"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["text"] == "@agent, please fix my grammar."
            assert data["timing_ms"] == 12.3
            mock_complete.assert_called_once()


@pytest.mark.asyncio
async def test_empty_content_gives_422():
    """Empty or whitespace-only content returns 422 with no LLM call."""
    with patch(
        "app.services.llm_service.complete",
        new=AsyncMock(side_effect=AssertionError("LLM must not be called")),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            for content in ("", "   "):
                resp = await client.post("/v1/agent", json={"content": content})
                assert resp.status_code == 422
                assert resp.json()["detail"] == "Nothing to process"


@pytest.mark.asyncio
async def test_content_too_long():
    """Content > 10,000 characters returns 422 Unprocessable Entity."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/agent",
            json={"content": "x" * 10001},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "Content exceeds 10000 characters limit" in data["detail"]


@pytest.mark.asyncio
async def test_empty_llm_fails_502():
    """Mock LLM returning empty text after retry raises 502 Bad Gateway."""
    empty_result = LLMResult(
        text="",
        elapsed_ms=30.0,
        prompt_tokens=10,
        completion_tokens=0,
        cached_tokens=0,
        reasoning_tokens=0,
    )
    with patch(
        "app.services.llm_service.complete",
        new=AsyncMock(return_value=empty_result),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/agent",
                json={"content": "Please format this text"},
            )
            assert resp.status_code == 502


@pytest.mark.asyncio
async def test_rate_limited_429():
    """Upstream RateLimitedError returns 429 status code."""
    with patch(
        "app.services.llm_service.complete",
        new=AsyncMock(
            side_effect=RateLimitedError("Meta API rate limit exceeded")
        ),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/agent",
                json={"content": "Fix spelling mistakes here"},
            )
            assert resp.status_code == 429
            data = resp.json()
            assert "Meta API rate limit exceeded" in data["detail"]
