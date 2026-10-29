import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import MetaApiError, RateLimitedError
from app.services.action_service import (
    SPARK_SYSTEM_PROMPT,
    Action,
    ActionResult,
    process,
)
from app.services.llm_service import LLMResult


def make_mock_reply(
    text: str,
    elapsed_ms: float = 120.0,
    prompt_tokens: int = 50,
    completion_tokens: int = 25,
    cached_tokens: int = 10,
    reasoning_tokens: int = 5,
) -> LLMResult:
    return LLMResult(
        text=text,
        elapsed_ms=elapsed_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        reasoning_tokens=reasoning_tokens,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply_json, expected_type, expected_text, expected_find",
    [
        (
            json.dumps({"type": "insert", "text": "hello"}),
            "insert",
            "hello",
            None,
        ),
        (
            json.dumps({"type": "replace", "find": "world", "text": "everyone"}),
            "replace",
            "everyone",
            "world",
        ),
        (
            json.dumps({"type": "rewrite", "text": "complete new text"}),
            "rewrite",
            "complete new text",
            None,
        ),
    ],
)
async def test_valid_actions_pass_through_without_fallback(
    reply_json, expected_type, expected_text, expected_find
):
    mock_complete = AsyncMock(return_value=make_mock_reply(reply_json))

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        res = await process(spoken_text="test command", box_text="hello world")

    assert isinstance(res, ActionResult)
    assert res.used_fallback is False
    assert res.fallback_reason is None
    assert res.action is not None
    assert res.action.type == expected_type
    assert res.action.text == expected_text
    assert res.action.find == expected_find
    assert res.elapsed_ms == 120.0
    assert res.prompt_tokens == 50
    assert res.completion_tokens == 25


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_exc",
    [
        RateLimitedError("Meta API rate limit exceeded"),
        MetaApiError("Meta API request failed"),
    ],
)
async def test_spark_error_falls_back_to_plain_insert(error_exc):
    mock_complete = AsyncMock(side_effect=error_exc)

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        res = await process(
            spoken_text="original spoken text",
            box_text="existing box text",
        )

    assert res.used_fallback is True
    assert res.fallback_reason == "spark_error"
    assert res.action == Action(type="insert", text="original spoken text")
    assert res.elapsed_ms == 0.0
    assert res.prompt_tokens == 0
    assert res.completion_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_reply_text",
    [
        "",  # empty reply
        "   ",  # whitespace reply
        "{not valid json",  # bad json
        json.dumps({"type": "unknown", "text": "hi"}),  # rule violation: bad type
        json.dumps({"type": "insert"}),  # rule violation: missing text
        json.dumps({"type": "replace", "text": "only text"}),  # missing find
        json.dumps({"type": "replace", "find": "", "text": "new"}),  # empty find
        json.dumps(["not", "a", "dict"]),  # list instead of dict
    ],
)
async def test_bad_replies_fallback_to_plain_insert(bad_reply_text):
    mock_complete = AsyncMock(return_value=make_mock_reply(bad_reply_text))

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        res = await process(spoken_text="fallback voice", box_text="box text")

    assert res.used_fallback is True
    assert res.fallback_reason == "bad_reply"
    assert res.action == Action(type="insert", text="fallback voice")
    assert res.elapsed_ms == 120.0
    assert res.prompt_tokens == 50


@pytest.mark.asyncio
async def test_replace_find_not_found_returns_none_action_no_insert():
    reply_json = json.dumps({"type": "replace", "find": "nonexistent", "text": "sub"})
    mock_complete = AsyncMock(return_value=make_mock_reply(reply_json))

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        res = await process(
            spoken_text="replace nonexistent",
            box_text="The quick brown fox",
        )

    assert res.used_fallback is True
    assert res.fallback_reason == "find_not_found"
    assert res.action is None
    # Ensure tokens and elapsed time from Spark reply are preserved
    assert res.elapsed_ms == 120.0
    assert res.prompt_tokens == 50


@pytest.mark.asyncio
async def test_replace_case_insensitive_match_corrected_to_box_text():
    # Box text has "Hello World", Spark returned lowercase "hello world"
    reply_json = json.dumps(
        {"type": "replace", "find": "hello world", "text": "Greetings"}
    )
    mock_complete = AsyncMock(return_value=make_mock_reply(reply_json))

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        res = await process(
            spoken_text="replace hello world",
            box_text="Say Hello World to all",
        )

    assert res.used_fallback is False
    assert res.fallback_reason is None
    assert res.action is not None
    assert res.action.type == "replace"
    assert res.action.find == "Hello World"  # Corrected to exact box slice
    assert res.action.text == "Greetings"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply_json, action_type",
    [
        (json.dumps({"type": "replace", "find": "foo", "text": "bar"}), "replace"),
        (json.dumps({"type": "rewrite", "text": "brand new"}), "rewrite"),
    ],
)
async def test_replace_or_rewrite_with_empty_box_falls_back_to_plain_insert(
    reply_json, action_type
):
    mock_complete = AsyncMock(return_value=make_mock_reply(reply_json))

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        res = await process(spoken_text="say something", box_text="   ")

    assert res.used_fallback is True
    assert res.fallback_reason == "not_allowed_empty_box"
    assert res.action == Action(type="insert", text="say something")


@pytest.mark.asyncio
@pytest.mark.parametrize("empty_speech", ["", "   ", "\t\n"])
async def test_empty_or_whitespace_spoken_text_returns_none_without_spark_call(
    empty_speech,
):
    mock_complete = AsyncMock()

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        res = await process(spoken_text=empty_speech, box_text="current text")

    assert res.action is None
    assert res.used_fallback is False
    assert res.fallback_reason == "empty_speech"
    assert res.elapsed_ms == 0.0
    assert res.prompt_tokens == 0
    # Spark must NOT be called
    mock_complete.assert_not_called()


@pytest.mark.asyncio
async def test_text_cleaning_removes_box_and_spoken_tags():
    mock_complete = AsyncMock(
        return_value=make_mock_reply(json.dumps({"type": "insert", "text": "clean"}))
    )

    dirty_box = "Before <box>in the box</box> and <BOX>upper</BOX>"
    dirty_spoken = "Do <spoken>this</spoken> and </SPOKEN>"

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        await process(spoken_text=dirty_spoken, box_text=dirty_box)

    mock_complete.assert_awaited_once()
    called_user_msg = mock_complete.call_args.args[1]

    # Verify literal tags are stripped from the message sent to Spark
    assert "<box>Before in the box and upper</box>" in called_user_msg
    assert "<spoken>Do this and </spoken>" in called_user_msg
    assert "<box>in the box</box>" not in called_user_msg
    assert "<BOX>" not in called_user_msg
    assert "</SPOKEN>" not in called_user_msg


@pytest.mark.asyncio
async def test_spark_call_has_system_prompt_first_and_user_message_last():
    mock_complete = AsyncMock(
        return_value=make_mock_reply(json.dumps({"type": "insert", "text": "ok"}))
    )

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        await process(spoken_text="my spoken text", box_text="my box text")

    mock_complete.assert_awaited_once()
    args = mock_complete.call_args.args
    assert args[0] == SPARK_SYSTEM_PROMPT
    assert "<box>my box text</box>\n<spoken>my spoken text</spoken>" == args[1]


@pytest.mark.asyncio
async def test_caplog_zero_text_leak_privacy(caplog):
    from loguru import logger

    handler_id = logger.add(caplog.handler, format="{message}")
    secret_box = "PRIVATE_BOX_CREDENTIAL_12345"
    secret_spoken = "PRIVATE_SPOKEN_SECRET_PASSWORD"
    secret_reply = "PRIVATE_REPLY_LEAK_CONTENT"

    mock_complete = AsyncMock(
        return_value=make_mock_reply(
            json.dumps({"type": "insert", "text": secret_reply})
        )
    )

    try:
        with patch("app.services.action_service.llm_service.complete", mock_complete):
            await process(spoken_text=secret_spoken, box_text=secret_box)

        # Privacy check: Ensure spoken words, box content, or reply text never leak
        assert secret_box not in caplog.text
        assert secret_spoken not in caplog.text
        assert secret_reply not in caplog.text
        assert "elapsed_ms=" in caplog.text
        assert "action_type=insert" in caplog.text
    finally:
        logger.remove(handler_id)
