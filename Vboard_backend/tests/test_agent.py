import asyncio
import json
from typing import Any
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


def _tool_call(call_id: str, query: str) -> MagicMock:
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = "web_search"
    tc.function.arguments = json.dumps({"query": query})
    return tc


def _llm_text(text: str) -> LLMResult:
    return LLMResult(
        text=text,
        elapsed_ms=10.0,
        prompt_tokens=5,
        completion_tokens=5,
        cached_tokens=0,
        reasoning_tokens=0,
        tool_calls=[],
    )


def _llm_tool_call(call_id: str, query: str) -> LLMResult:
    return LLMResult(
        text="",
        elapsed_ms=10.0,
        prompt_tokens=5,
        completion_tokens=5,
        cached_tokens=0,
        reasoning_tokens=0,
        tool_calls=[_tool_call(call_id, query)],
    )


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
async def test_agent_alone_gives_422():
    """@agent alone (or only spaces after it) returns 422 with no LLM call."""
    with patch(
        "app.services.llm_service.complete_messages",
        new=AsyncMock(side_effect=AssertionError("LLM must not be called")),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            for content in ("@agent", "@agent   ", "  @agent  "):
                resp = await client.post("/v1/agent", json={"content": content})
                assert resp.status_code == 422
                assert (
                    resp.json()["detail"] == "Type what you want after @agent"
                )


@pytest.mark.asyncio
async def test_empty_content_gives_422():
    """Empty or whitespace-only content returns 422 with no LLM call."""
    with patch(
        "app.services.llm_service.complete",
        new=AsyncMock(side_effect=AssertionError("LLM must not be called")),
    ), patch(
        "app.services.llm_service.complete_messages",
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
async def test_agent_generates_text():
    """@agent\\nTask returns generated text without search."""
    with patch(
        "app.services.llm_service.complete_messages",
        new=AsyncMock(return_value=_llm_text("Happy birthday, Anil!")),
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
            assert data["text"] == "Happy birthday, Anil!"
            assert data["used_search"] is False
            assert data["rounds"] == 1


@pytest.mark.asyncio
async def test_out_of_scope_returns_original():
    """Model marker returns the original content unchanged with note."""
    original = "@agent\nTurn this water into wine by tomorrow"
    with patch(
        "app.services.llm_service.complete_messages",
        new=AsyncMock(return_value=_llm_text("x [[OUT_OF_SCOPE]] y")),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post("/v1/agent", json={"content": original})
            assert resp.status_code == 200
            data = resp.json()
            assert data["text"] == original
            assert data["note"] == "out_of_scope"
            assert "[[OUT_OF_SCOPE]]" not in data["text"]


@pytest.mark.asyncio
async def test_agent_search_disabled(monkeypatch):
    """When AGENT_SEARCH_ENABLED=False, no tools key is sent."""
    monkeypatch.setattr(settings, "AGENT_SEARCH_ENABLED", False)

    choice = MagicMock()
    choice.message.content = "Python is a versatile programming language."
    choice.message.tool_calls = None
    mock_resp = MagicMock(choices=[choice])
    mock_resp.usage = None
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)

    with patch(
        "app.services.llm_service.get_llm_client", return_value=mock_client
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

            kwargs = mock_client.chat.completions.create.call_args[1]
            assert "tools" not in kwargs


@pytest.mark.asyncio
async def test_transport_forwards_tools_choice_history_and_minimal():
    """Tools, tool_choice and full history reach the request; forced is none."""
    tc1 = MagicMock()
    tc1.id = "call_round1"
    tc1.function.name = "web_search"
    tc1.function.arguments = json.dumps({"query": "Mysuru places"})
    choice1 = MagicMock()
    choice1.message.content = None
    choice1.message.tool_calls = [tc1]
    resp1 = MagicMock(choices=[choice1])
    resp1.usage = None

    tc2 = MagicMock()
    tc2.id = "call_round2"
    tc2.function.name = "web_search"
    tc2.function.arguments = json.dumps({"query": "Mysuru palace timing"})
    choice2 = MagicMock()
    choice2.message.content = None
    choice2.message.tool_calls = [tc2]
    resp2 = MagicMock(choices=[choice2])
    resp2.usage = None

    choice3 = MagicMock()
    choice3.message.content = "Visit the palace, Chamundi Hills and market."
    choice3.message.tool_calls = None
    resp3 = MagicMock(choices=[choice3])
    resp3.usage = None

    mock_client = MagicMock()
    scripted = [resp1, resp2, resp3]
    seen: list[dict[str, Any]] = []

    async def _fake_create(**kwargs: Any) -> Any:
        # Snapshot now: agent_service mutates the messages list afterwards.
        seen.append(
            {
                "has_tools": "tools" in kwargs,
                "tool_choice": kwargs.get("tool_choice"),
                "reasoning_effort": kwargs.get("reasoning_effort"),
                "message_count": len(kwargs["messages"]),
            }
        )
        return scripted[len(seen) - 1]

    mock_client.chat.completions.create = _fake_create

    with patch(
        "app.services.llm_service.get_llm_client", return_value=mock_client
    ), patch(
        "app.services.search_service.search",
        new=AsyncMock(return_value="Palace timings 10am-5:30pm"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/agent",
                json={"content": "@agent\nName 3 places to visit in Mysuru"},
            )
            assert resp.status_code == 200

    assert len(seen) == 3

    first = seen[0]
    assert first["has_tools"] is True
    assert first["tool_choice"] == "auto"
    assert first["reasoning_effort"] == "minimal"
    assert first["message_count"] == 2

    second = seen[1]
    assert second["has_tools"] is True
    assert second["tool_choice"] == "auto"
    assert second["reasoning_effort"] == "minimal"
    # system + user + assistant(tool_call) + tool(result)
    assert second["message_count"] == 4

    forced = seen[2]
    assert forced["tool_choice"] == "none"
    assert forced["reasoning_effort"] == "minimal"
    # forced final carries the full two-round history
    assert forced["message_count"] == 6


@pytest.mark.asyncio
async def test_agent_with_search_mock():
    """Mock tool call triggering search, verifying search and multiple rounds."""
    with patch(
        "app.services.llm_service.complete_messages",
        new=AsyncMock(
            side_effect=[
                _llm_tool_call("call_abc123", "FastAPI release date"),
                _llm_text("FastAPI was first released in December 2018."),
            ]
        ),
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
async def test_agent_empty_after_retry_502():
    """Agent returning empty text twice raises 502."""
    with patch(
        "app.services.llm_service.complete_messages",
        new=AsyncMock(return_value=_llm_text("")),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/v1/agent",
                json={"content": "@agent\nWrite something inspiring"},
            )
            assert resp.status_code == 502


@pytest.mark.asyncio
async def test_search_timeout_fallback():
    """Mock search raising TimeoutError returns 200 with search_timeout note."""
    with patch(
        "app.services.llm_service.complete_messages",
        new=AsyncMock(
            side_effect=[
                _llm_tool_call("call_timeout123", "latest news"),
                _llm_text("Search was unavailable, but here is what I know."),
            ]
        ),
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
