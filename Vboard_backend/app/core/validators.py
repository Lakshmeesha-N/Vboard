import re
from typing import Optional

from loguru import logger

from app.core.audio import META_SUPPORTED_LANGUAGES
from app.core.config import settings
from app.core.exceptions import InvalidRequestError

DEVICE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_CANONICAL_LANGUAGE_MAP: dict[str, str] = {
    lang.lower(): lang for lang in META_SUPPORTED_LANGUAGES
}


def validate_device_id(device_id: Optional[str]) -> Optional[str]:
    """
    Validate device identifier format and log validated ID.

    Raises:
        InvalidRequestError: If device_id does not match [a-zA-Z0-9_-]{1,64}.
    """
    if device_id is None:
        return None

    if not DEVICE_ID_PATTERN.match(device_id):
        raise InvalidRequestError(
            "Invalid device_id: must be 1-64 alphanumeric "
            "characters, underscores, or hyphens"
        )

    # Log ONLY the validated device identifier
    logger.info("Processing audio request for device: {}", device_id)
    return device_id


def validate_context_text(context_text: Optional[str]) -> Optional[str]:
    """
    Validate context_text length without logging its content.

    Raises:
        InvalidRequestError: If context_text exceeds maximum character limit.
    """
    if context_text is None:
        return None

    if len(context_text) > settings.MAX_CONTEXT_TEXT_LENGTH:
        raise InvalidRequestError(
            f"context_text exceeds maximum limit of "
            f"{settings.MAX_CONTEXT_TEXT_LENGTH} characters"
        )

    # Strictly never logged for user privacy
    return context_text


def parse_languages(languages: Optional[str]) -> Optional[list[str]]:
    """
    Parse, canonicalize, and validate language hints.

    - Matches case-insensitively against Meta's 25 supported languages.
    - Drops unknown language names silently.
    - Trims to first 5 valid languages if more than 5 are provided.
    - Returns None if no valid languages remain.
    """
    if not languages:
        return None

    valid_langs: list[str] = []
    seen: set[str] = set()

    for item in languages.split(","):
        cleaned = item.strip().lower()
        if not cleaned:
            continue
        canonical = _CANONICAL_LANGUAGE_MAP.get(cleaned)
        if canonical and canonical not in seen:
            seen.add(canonical)
            valid_langs.append(canonical)

    if not valid_langs:
        return None

    # Trim to maximum allowed languages count (5)
    return valid_langs[: settings.MAX_LANGUAGES_COUNT]
