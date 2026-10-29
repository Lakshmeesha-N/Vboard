import pytest

from app.core.exceptions import InvalidRequestError
from app.core.validators import (
    parse_languages,
    validate_context_text,
    validate_device_id,
)


def test_validate_device_id_valid():
    assert validate_device_id("pixel-7_pro") == "pixel-7_pro"
    assert validate_device_id(None) is None


def test_validate_device_id_invalid_chars():
    with pytest.raises(InvalidRequestError) as exc_info:
        validate_device_id("device@123!")
    assert exc_info.value.status_code == 400
    assert "invalid device_id" in str(exc_info.value).lower()


def test_validate_device_id_too_long():
    with pytest.raises(InvalidRequestError) as exc_info:
        validate_device_id("a" * 65)
    assert exc_info.value.status_code == 400


def test_validate_context_text_valid():
    text = "User typing a message"
    assert validate_context_text(text) == text
    assert validate_context_text(None) is None


def test_validate_context_text_too_long():
    with pytest.raises(InvalidRequestError) as exc_info:
        validate_context_text("A" * 10001)
    assert exc_info.value.status_code == 400
    assert "exceeds maximum limit" in str(exc_info.value).lower()


def test_parse_languages_none_or_empty():
    assert parse_languages(None) is None
    assert parse_languages("") is None
    assert parse_languages("   ,  , ") is None


def test_parse_languages_case_insensitive_and_canonicalized():
    res = parse_languages(" kannada , ENGLISH , hinDi ")
    assert res == ["Kannada", "English", "Hindi"]


def test_parse_languages_drops_unknown_names():
    res = parse_languages("Kannada, Klingon, English, Elvish")
    assert res == ["Kannada", "English"]


def test_parse_languages_only_unknown_returns_none():
    res = parse_languages("Klingon, Elvish, Dothraki")
    assert res is None


def test_parse_languages_trims_to_five_max():
    raw = "kannada, english, hindi, tamil, telugu, spanish, french"
    res = parse_languages(raw)
    assert res == ["Kannada", "English", "Hindi", "Tamil", "Telugu"]
    assert len(res) == 5
