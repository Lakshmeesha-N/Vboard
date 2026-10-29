import inspect
import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from app.core.config import settings
from app.core.exceptions import MetaApiError, RateLimitedError
from app.prompts import SPARK_SYSTEM_PROMPT
from app.schemas.actions import Action
from app.services import llm_service

ACTION_RESPONSE_FORMAT = {"type": "json_object"}


@dataclass(frozen=True)
class ActionResult:
    """Action service result with execution metrics and fallback state."""

    action: Optional[Action]
    used_fallback: bool
    fallback_reason: Optional[str]
    elapsed_ms: float
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    reasoning_tokens: int


def clean_text(text: str) -> str:
    """Remove literal <box>, </box>, <spoken>, </spoken> tags (case-insensitive)."""
    return re.sub(r"(?i)</?(?:box|spoken)>", "", text)


def build_user_message(box: str, spoken: str) -> str:
    """Build the exact XML-tagged user prompt."""
    return f"<box>{box}</box>\n<spoken>{spoken}</spoken>"


def parse_action(reply_text: str) -> Optional[Action]:
    """
    Parse and validate JSON action reply strictly.

    Requires 'action', 'text', 'find'. Does NOT accept 'type'.
    'which' defaults to 'last' only when omitted.
    """
    if not reply_text or not reply_text.strip():
        return None

    cleaned = reply_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    # Strict requirement: Do not accept "type", must have "action"
    if "type" in data and "action" not in data:
        return None

    action_name = data.get("action")
    if action_name not in ("insert", "replace", "rewrite"):
        return None

    text = data.get("text")
    if not isinstance(text, str):
        return None

    find = data.get("find")
    if not isinstance(find, str):
        return None

    which = data.get("which", "last")
    if not isinstance(which, str) or not which.strip():
        which = "last"

    if action_name == "replace" and not find.strip():
        return None

    return Action(action=action_name, text=text, find=find, which=which)


async def process(
    spoken_text: str,
    box_text: str,
    reasoning_effort: Optional[str] = None,
) -> ActionResult:
    """
    Process speech input against box text, determining editing action via Spark.

    Args:
        spoken_text: Transcribed voice text.
        box_text: Existing text in the input box.
        reasoning_effort: Optional reasoning effort override for Spark.

    Returns:
        ActionResult containing action, fallback flags, and numeric metrics.
    """
    # 2a. If spoken_text is empty or whitespace only: return empty_speech
    if not spoken_text or not spoken_text.strip():
        logger.info(
            "Action result: elapsed_ms=0.00, prompt_tokens=0, completion_tokens=0, "
            "cached_tokens=0, reasoning_tokens=0, action_type=None, "
            "used_fallback=False, fallback_reason=empty_speech"
        )
        return ActionResult(
            action=None,
            used_fallback=False,
            fallback_reason="empty_speech",
            elapsed_ms=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            cached_tokens=0,
            reasoning_tokens=0,
        )

    # 2b. Clean tags from both texts
    cleaned_box = clean_text(box_text)
    cleaned_spoken = clean_text(spoken_text)

    # 2c. Build exact user message
    user_message = build_user_message(cleaned_box, cleaned_spoken)

    # 2d. Call Spark via llm_service
    effort = (
        reasoning_effort
        if reasoning_effort is not None
        else settings.SPARK_REASONING_EFFORT
    )

    try:
        # Pass kwargs dynamically if accepted by signature or mock
        sig = inspect.signature(llm_service.complete)
        kwargs: dict[str, Any] = {}
        has_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        if "response_format" in sig.parameters or has_var_kw:
            kwargs["response_format"] = ACTION_RESPONSE_FORMAT
        if "reasoning_effort" in sig.parameters or has_var_kw:
            kwargs["reasoning_effort"] = effort

        reply = await llm_service.complete(
            SPARK_SYSTEM_PROMPT,
            user_message,
            **kwargs,
        )
    except (RateLimitedError, MetaApiError):
        # 2e. Catch ONLY RateLimitedError and MetaApiError -> spark_error fallback
        action = Action(action="insert", text=spoken_text, find="", which="last")
        used_fallback = True
        fallback_reason = "spark_error"
        logger.info(
            "Action result: elapsed_ms=0.00, prompt_tokens=0, completion_tokens=0, "
            "cached_tokens=0, reasoning_tokens=0, action_type={}, "
            "used_fallback={}, fallback_reason={}",
            action.action,
            used_fallback,
            fallback_reason,
        )
        return ActionResult(
            action=action,
            used_fallback=used_fallback,
            fallback_reason=fallback_reason,
            elapsed_ms=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            cached_tokens=0,
            reasoning_tokens=0,
        )

    elapsed_ms = reply.elapsed_ms
    prompt_tokens = reply.prompt_tokens
    completion_tokens = reply.completion_tokens
    cached_tokens = reply.cached_tokens
    reasoning_tokens = reply.reasoning_tokens

    # 2f. Parse action reply
    parsed = parse_action(reply.text)
    if parsed is None:
        action = Action(action="insert", text=spoken_text, find="", which="last")
        used_fallback = True
        fallback_reason = "bad_reply"
    # 2g. Empty box check for replace or rewrite
    elif not box_text.strip() and parsed.action in ("replace", "rewrite"):
        action = Action(action="insert", text=spoken_text, find="", which="last")
        used_fallback = True
        fallback_reason = "not_allowed_empty_box"
    # 2h. Replace reconciliation
    elif parsed.action == "replace":
        find_target = parsed.find
        if find_target in box_text:
            action = parsed
            used_fallback = False
            fallback_reason = None
        else:
            match = re.search(re.escape(find_target), box_text, re.IGNORECASE)
            if match:
                parsed.find = match.group(0)
                action = parsed
                used_fallback = False
                fallback_reason = None
            else:
                action = None
                used_fallback = True
                fallback_reason = "find_not_found"
    # 2i. Normal valid action
    else:
        action = parsed
        used_fallback = False
        fallback_reason = None

    action_type = action.action if action else None
    logger.info(
        "Action result: elapsed_ms={:.2f}, prompt_tokens={}, completion_tokens={}, "
        "cached_tokens={}, reasoning_tokens={}, action_type={}, "
        "used_fallback={}, fallback_reason={}",
        elapsed_ms,
        prompt_tokens,
        completion_tokens,
        cached_tokens,
        reasoning_tokens,
        action_type,
        used_fallback,
        fallback_reason,
    )

    return ActionResult(
        action=action,
        used_fallback=used_fallback,
        fallback_reason=fallback_reason,
        elapsed_ms=elapsed_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        reasoning_tokens=reasoning_tokens,
    )
