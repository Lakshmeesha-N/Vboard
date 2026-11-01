import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.config import settings
from app.core.exceptions import RateLimitedError
from app.main import app
from app.services.llm_service import LLMResult


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_cleanup_default():
    """Normal text without @agent routes to cleanup, returns corrected text."""
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
            assert data["used_search"] is False
            assert data["rounds"] == 1
            assert data["note"] is None
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
            assert data["used_search"] is False
            assert data["rounds"] == 1


@pytest.mark.asyncio
async def test_agent_empty_task():
    """@agent alone returns 'Please describe your task.' with 200 OK."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        resp = await client.post(
            "/v1/agent",
            json={"content": "@agent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "Please describe your task."
        assert data["used_search"] is False
        assert data["rounds"] == 0
        assert data["note"] is None
        assert data["timing_ms"] == 0.0


@pytest.mark.asyncio
async def test_agent_generates_text():
    """@agent\\nTask returns generated text without search."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Wishing you a fantastic 30th birthday, Anil!"
    mock_choice.message.tool_calls = None
    mock_resp = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.services.agent_service.get_llm_client",
        return_value=mock_client,
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/agent",
                json={
                    "content": "@agent\nWrite birthday wishes\nfor Anil turning 30"
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert (
                data["text"] == "Wishing you a fantastic 30th birthday, Anil!"
            )
            assert data["used_search"] is False
            assert data["rounds"] == 1


@pytest.mark.asyncio
async def test_agent_search_disabled(monkeypatch):
    """When AGENT_SEARCH_ENABLED=False, no tools are passed or invoked."""
    monkeypatch.setattr(settings, "AGENT_SEARCH_ENABLED", False)

    mock_choice = MagicMock()
    mock_choice.message.content = "Python is a versatile programming language."
    mock_choice.message.tool_calls = None
    mock_resp = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.services.agent_service.get_llm_client",
        return_value=mock_client,
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/agent",
                json={"content": "@agent\nExplain Python"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert (
                data["text"] == "Python is a versatile programming language."
            )
            assert data["used_search"] is False
            assert data["rounds"] == 1

            # Verify no tools were passed to the completions endpoint
            kwargs = mock_client.chat.completions.create.call_args[1]
            assert "tools" not in kwargs or kwargs["tools"] is None


@pytest.mark.asyncio
async def test_agent_with_search_mock():
    """Mock tool call triggering search, verifying search and multiple rounds."""
    tc = MagicMock()
    tc.id = "call_abc123"
    tc.function.name = "web_search"
    tc.function.arguments = json.dumps({"query": "FastAPI release date"})

    choice_round1 = MagicMock()
    choice_round1.message.content = None
    choice_round1.message.tool_calls = [tc]
    resp_round1 = MagicMock(choices=[choice_round1])

    choice_round2 = MagicMock()
    choice_round2.message.content = "FastAPI was first released in December 2018."
    choice_round2.message.tool_calls = None
    resp_round2 = MagicMock(choices=[choice_round2])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[resp_round1, resp_round2]
    )

    with patch(
        "app.services.agent_service.get_llm_client",
        return_value=mock_client,
    ), patch(
        "app.services.search_service.search",
        new=AsyncMock(return_value="FastAPI Initial release December 5, 2018"),
    ) as mock_search:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/agent",
                json={"content": "@agent\nWhen was FastAPI released?"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert (
                data["text"]
                == "FastAPI was first released in December 2018."
            )
            assert data["used_search"] is True
            assert data["rounds"] == 2
            assert data["note"] is None
            mock_search.assert_called_once_with(
                "FastAPI release date", timeout=8.0
            )


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
async def test_search_timeout_fallback():
    """Mock search raising TimeoutError returns 200 with search_timeout note."""
    tc = MagicMock()
    tc.id = "call_timeout123"
    tc.function.name = "web_search"
    tc.function.arguments = json.dumps({"query": "latest news"})

    choice_round1 = MagicMock()
    choice_round1.message.content = None
    choice_round1.message.tool_calls = [tc]
    resp_round1 = MagicMock(choices=[choice_round1])

    choice_forced = MagicMock()
    choice_forced.message.content = "Search was unavailable, but here is what I know."
    choice_forced.message.tool_calls = None
    resp_forced = MagicMock(choices=[choice_forced])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        side_effect=[resp_round1, resp_forced]
    )

    with patch(
        "app.services.agent_service.get_llm_client",
        return_value=mock_client,
    ), patch(
        "app.services.search_service.search",
        new=AsyncMock(side_effect=asyncio.TimeoutError()),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/agent",
                json={"content": "@agent\nWhat is the latest news?"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert (
                data["text"]
                == "Search was unavailable, but here is what I know."
            )
            assert data["used_search"] is True
            assert data["rounds"] == 1
            assert data["note"] == "search_timeout"


@pytest.mark.asyncio
async def test_rate_limited_429():
    """Upstream RateLimitedError returns 429 status code."""
    with patch(
        "app.services.llm_service.complete",
        new=AsyncMock(side_effect=RateLimitedError("Meta API rate limit exceeded")),
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
