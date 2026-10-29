import json
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator


class Action(BaseModel):
    """Strict editing action structure for keyboard operations."""

    model_config = ConfigDict(extra="ignore", strict=True)

    action: Literal["insert", "replace", "rewrite"]
    text: str
    find: str
    which: Literal["first", "last", "all"] = "last"

    @model_validator(mode="before")
    @classmethod
    def preprocess(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            action = data.get("action")
            # For insert and rewrite, ignore the value and set it to "last"
            if action in ("insert", "rewrite"):
                data["which"] = "last"
            elif action == "replace":
                # Missing which means "last"
                if "which" not in data or data.get("which") is None:
                    data["which"] = "last"
                elif data.get("which") not in ("first", "last", "all"):
                    raise ValueError(f"Invalid which for replace: {data.get('which')}")
        return data

    @model_validator(mode="after")
    def validate_semantics(self) -> "Action":
        if self.action in ("insert", "rewrite"):
            if not self.text.strip():
                raise ValueError(f"{self.action} requires non-empty text")
        elif self.action == "replace":
            if not self.find.strip():
                raise ValueError("replace requires non-empty find")
        return self


def parse_action(reply_text: str) -> Optional[Action]:
    """
    Parse and validate JSON action reply strictly.

    Requires 'action', 'text', 'find'. Does NOT accept 'type' alone.
    'which' defaults to 'last' when omitted.
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

    try:
        return Action.model_validate(data)
    except (ValidationError, ValueError, TypeError):
        return None


def _build_action_response_format() -> dict[str, Any]:
    """Build response_format schema dict with all 4 fields required and strict mode."""
    schema = Action.model_json_schema()
    schema["required"] = ["action", "text", "find", "which"]
    schema["additionalProperties"] = False
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "Action",
            "strict": True,
            "schema": schema,
        },
    }


ACTION_RESPONSE_FORMAT = _build_action_response_format()
