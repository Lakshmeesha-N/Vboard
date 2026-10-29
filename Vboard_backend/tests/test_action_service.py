import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import MetaApiError, RateLimitedError
from app.services.action_service import (
    ACTION_RESPONSE_FORMAT,
    SPARK_SYSTEM_PROMPT,
    Action,
    ActionResult,
    parse_action,
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


def test_spark_system_prompt_content():
    """Verify prompt is non-empty and contains required action and which keywords."""
    assert SPARK_SYSTEM_PROMPT
    prompt_lower = SPARK_SYSTEM_PROMPT.lower()
    for keyword in ("insert", "replace", "rewrite", "first", "last", "all"):
        assert keyword in prompt_lower, f"Keyword '{keyword}' missing from prompt"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply_json, expected_action, expected_text, expected_find, expected_which",
    [
        (
            json.dumps(
                {
                    "action": "insert",
                    "text": "hello",
                    "find": "",
                    "which": "last",
                }
            ),
            "insert",
            "hello",
            "",
            "last",
        ),
        (
            json.dumps(
                {
                    "action": "replace",
                    "find": "world",
                    "text": "everyone",
                    "which": "last",
                }
            ),
            "replace",
            "everyone",
            "world",
            "last",
        ),
        (
            json.dumps(
                {
                    "action": "rewrite",
                    "text": "complete new text",
                    "find": "",
                    "which": "last",
                }
            ),
            "rewrite",
            "complete new text",
            "",
            "last",
        ),
    ],
)
async def test_valid_actions_pass_through_without_fallback(
    reply_json,
    expected_action,
    expected_text,
    expected_find,
    expected_which,
):
    mock_complete = AsyncMock(return_value=make_mock_reply(reply_json))

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        res = await process(spoken_text="test command", box_text="hello world")

    assert isinstance(res, ActionResult)
    assert res.used_fallback is False
    assert res.fallback_reason is None
    assert res.action is not None
    assert res.action.action == expected_action
    assert res.action.text == expected_text
    assert res.action.find == expected_find
    assert res.action.which == expected_which
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
    assert res.action == Action(
        action="insert", text="original spoken text", find="", which="last"
    )
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
        json.dumps(
            {
                "action": "unknown",
                "text": "hi",
                "find": "",
                "which": "last",
            }
        ),  # bad action
        json.dumps(
            {
                "action": "insert",
                "find": "",
                "which": "last",
            }
        ),  # missing text
        json.dumps(
            {
                "action": "replace",
                "text": "only text",
                "which": "last",
            }
        ),  # missing find
        json.dumps(
            {
                "action": "replace",
                "find": "",
                "text": "new",
                "which": "last",
            }
        ),  # empty find on replace
        json.dumps(
            {
                "type": "insert",
                "text": "hello",
                "find": "",
                "which": "last",
            }
        ),  # "type" is rejected
        json.dumps(["not", "a", "dict"]),  # list instead of dict
    ],
)
async def test_bad_replies_fallback_to_plain_insert(bad_reply_text):
    mock_complete = AsyncMock(return_value=make_mock_reply(bad_reply_text))

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        res = await process(spoken_text="fallback voice", box_text="box text")

    assert res.used_fallback is True
    assert res.fallback_reason == "bad_reply"
    assert res.action == Action(
        action="insert", text="fallback voice", find="", which="last"
    )
    assert res.elapsed_ms == 120.0
    assert res.prompt_tokens == 50


@pytest.mark.asyncio
async def test_replace_find_not_found_returns_none_action_no_insert():
    reply_json = json.dumps(
        {
            "action": "replace",
            "find": "nonexistent",
            "text": "sub",
            "which": "last",
        }
    )
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
        {
            "action": "replace",
            "find": "hello world",
            "text": "Greetings",
            "which": "last",
        }
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
    assert res.action.action == "replace"
    assert res.action.find == "Hello World"  # Corrected to exact box slice
    assert res.action.text == "Greetings"
    assert res.action.which == "last"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply_json, action_name",
    [
        (
            json.dumps(
                {
                    "action": "replace",
                    "find": "foo",
                    "text": "bar",
                    "which": "last",
                }
            ),
            "replace",
        ),
        (
            json.dumps(
                {
                    "action": "rewrite",
                    "text": "brand new",
                    "find": "",
                    "which": "last",
                }
            ),
            "rewrite",
        ),
    ],
)
async def test_replace_or_rewrite_with_empty_box_falls_back_to_plain_insert(
    reply_json, action_name
):
    mock_complete = AsyncMock(return_value=make_mock_reply(reply_json))

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        res = await process(spoken_text="say something", box_text="   ")

    assert res.used_fallback is True
    assert res.fallback_reason == "not_allowed_empty_box"
    assert res.action == Action(
        action="insert", text="say something", find="", which="last"
    )


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
        return_value=make_mock_reply(
            json.dumps(
                {
                    "action": "insert",
                    "text": "clean",
                    "find": "",
                    "which": "last",
                }
            )
        )
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
        return_value=make_mock_reply(
            json.dumps(
                {
                    "action": "insert",
                    "text": "ok",
                    "find": "",
                    "which": "last",
                }
            )
        )
    )

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        await process(spoken_text="my spoken text", box_text="my box text")

    mock_complete.assert_awaited_once()
    args = mock_complete.call_args.args
    assert args[0] == SPARK_SYSTEM_PROMPT
    assert "<box>my box text</box>\n<spoken>my spoken text</spoken>" == args[1]
    kwargs = mock_complete.call_args.kwargs
    assert kwargs["response_format"] == ACTION_RESPONSE_FORMAT
    assert kwargs["reasoning_effort"] == "minimal"


@pytest.mark.asyncio
async def test_spark_call_forwards_explicit_reasoning_effort():
    mock_complete = AsyncMock(
        return_value=make_mock_reply(
            json.dumps(
                {
                    "action": "insert",
                    "text": "ok",
                    "find": "",
                    "which": "last",
                }
            )
        )
    )

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        await process(
            spoken_text="hello",
            box_text="",
            reasoning_effort="high",
        )

    mock_complete.assert_awaited_once()
    kwargs = mock_complete.call_args.kwargs
    assert kwargs["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_caplog_zero_text_leak_privacy(caplog):
    from loguru import logger

    handler_id = logger.add(caplog.handler, format="{message}")
    secret_box = "PRIVATE_BOX_CREDENTIAL_12345"
    secret_spoken = "PRIVATE_SPOKEN_SECRET_PASSWORD"
    secret_reply = "PRIVATE_REPLY_LEAK_CONTENT"

    mock_complete = AsyncMock(
        return_value=make_mock_reply(
            json.dumps(
                {
                    "action": "insert",
                    "text": secret_reply,
                    "find": "",
                    "which": "last",
                }
            )
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


def test_which_validation_and_normalization():
    # 1. Invalid which for replace is rejected
    invalid_replace = json.dumps(
        {"action": "replace", "find": "old", "text": "new", "which": "middle"}
    )
    assert parse_action(invalid_replace) is None

    # 2. Valid which for replace is preserved
    for w in ("first", "last", "all"):
        valid_replace = json.dumps(
            {"action": "replace", "find": "old", "text": "new", "which": w}
        )
        parsed = parse_action(valid_replace)
        assert parsed is not None
        assert parsed.which == w

    # 3. Missing which for replace defaults to "last"
    missing_which_replace = json.dumps(
        {"action": "replace", "find": "old", "text": "new"}
    )
    parsed = parse_action(missing_which_replace)
    assert parsed is not None
    assert parsed.which == "last"

    # 4. For insert and rewrite, which is ignored and normalized to "last"
    for w in ("first", "all", "invalid_which", "middle"):
        ins = json.dumps(
            {"action": "insert", "text": "hello", "find": "", "which": w}
        )
        parsed_ins = parse_action(ins)
        assert parsed_ins is not None
        assert parsed_ins.which == "last"

        rew = json.dumps(
            {"action": "rewrite", "text": "hello world", "find": "", "which": w}
        )
        parsed_rew = parse_action(rew)
        assert parsed_rew is not None
        assert parsed_rew.which == "last"


@pytest.mark.parametrize("empty_val", ["", "   ", "\t\n"])
def test_empty_text_for_insert_and_rewrite_rejected(empty_val):
    bad_insert = json.dumps(
        {"action": "insert", "text": empty_val, "find": "", "which": "last"}
    )
    assert parse_action(bad_insert) is None

    bad_rewrite = json.dumps(
        {"action": "rewrite", "text": empty_val, "find": "", "which": "last"}
    )
    assert parse_action(bad_rewrite) is None


def test_empty_text_replace_allowed():
    # Replace with non-empty find and empty text is allowed (e.g. deletion)
    empty_text_replace = json.dumps(
        {"action": "replace", "find": "target", "text": "", "which": "first"}
    )
    parsed = parse_action(empty_text_replace)
    assert parsed is not None
    assert parsed.action == "replace"
    assert parsed.find == "target"
    assert parsed.text == ""
    assert parsed.which == "first"


@pytest.mark.asyncio
async def test_empty_text_replace_process_integration():
    mock_complete = AsyncMock(
        return_value=make_mock_reply(
            json.dumps(
                {
                    "action": "replace",
                    "find": "delete me",
                    "text": "",
                    "which": "last",
                }
            )
        )
    )

    with patch("app.services.action_service.llm_service.complete", mock_complete):
        res = await process(
            spoken_text="delete delete me",
            box_text="Please delete me now",
        )

    assert res.used_fallback is False
    assert res.fallback_reason is None
    assert res.action is not None
    assert res.action.action == "replace"
    assert res.action.find == "delete me"
    assert res.action.text == ""
    assert res.action.which == "last"


def test_type_only_reply_rejected_and_extra_keys_ignored():
    # Reply with only "type" instead of "action" is rejected
    type_only = json.dumps(
        {"type": "insert", "text": "hello", "find": "", "which": "last"}
    )
    assert parse_action(type_only) is None

    # Reply with both "action" and extra keys (including "type") is accepted with extra keys ignored
    with_extras = json.dumps(
        {
            "action": "insert",
            "type": "insert",
            "text": "hello",
            "find": "",
            "which": "last",
            "unexpected_field": 42,
        }
    )
    parsed = parse_action(with_extras)
    assert parsed is not None
    assert parsed.action == "insert"
    assert parsed.text == "hello"
    assert parsed.find == ""
    assert parsed.which == "last"

