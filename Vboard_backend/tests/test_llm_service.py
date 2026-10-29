from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import openai
import pytest

from app.core.exceptions import MetaApiError, RateLimitedError
from app.services.llm_service import LLMResult, complete


@pytest.mark.asyncio
async def test_complete_success_fills_dataclass_and_checks_order():
    mock_client = AsyncMock()
    mock_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="This is the model response.")
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=42,
            completion_tokens=18,
            prompt_tokens_details=SimpleNamespace(cached_tokens=10),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=5),
        ),
    )
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.services.llm_service.get_llm_client", return_value=mock_client):
        result = await complete(
            system_prompt="You are a helpful assistant.",
            user_text="Convert this speech into text.",
        )

    assert isinstance(result, LLMResult)
    assert result.text == "This is the model response."
    assert result.prompt_tokens == 42
    assert result.completion_tokens == 18
    assert result.cached_tokens == 10
    assert result.reasoning_tokens == 5
    assert result.elapsed_ms >= 0

    # Verify call parameters: model and message order (system first, user last)
    assert mock_client.chat.completions.create.call_count == 1
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "muse-spark-1.3"
    assert "response_format" not in call_kwargs
    assert "reasoning_effort" not in call_kwargs
    messages = call_kwargs["messages"]
    assert len(messages) == 2
    assert messages[0] == {"role": "system", "content": "You are a helpful assistant."}
    assert messages[1] == {"role": "user", "content": "Convert this speech into text."}


@pytest.mark.asyncio
async def test_complete_passes_optional_parameters_when_set():
    mock_client = AsyncMock()
    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        usage=None,
    )
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.services.llm_service.get_llm_client", return_value=mock_client):
        await complete(
            system_prompt="sys",
            user_text="usr",
            response_format={"type": "json_object"},
            reasoning_effort="minimal",
        )

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert call_kwargs["reasoning_effort"] == "minimal"


@pytest.mark.asyncio
async def test_complete_missing_usage_fields_default_to_zero():
    mock_client = AsyncMock()
    # Response with no usage details at all
    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Fallback response"))],
        usage=None,
    )
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.services.llm_service.get_llm_client", return_value=mock_client):
        result = await complete("system", "user")

    assert result.text == "Fallback response"
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
    assert result.cached_tokens == 0
    assert result.reasoning_tokens == 0


@pytest.mark.asyncio
async def test_complete_partial_usage_details_default_to_zero():
    mock_client = AsyncMock()
    # Response with usage present but details missing or None
    mock_response = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content="Partial usage response"))
        ],
        usage=SimpleNamespace(
            prompt_tokens=15,
            completion_tokens=None,
            prompt_tokens_details=None,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=None),
        ),
    )
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.services.llm_service.get_llm_client", return_value=mock_client):
        result = await complete("system", "user")

    assert result.text == "Partial usage response"
    assert result.prompt_tokens == 15
    assert result.completion_tokens == 0
    assert result.cached_tokens == 0
    assert result.reasoning_tokens == 0


@pytest.mark.asyncio
async def test_complete_maps_rate_limit_error():
    mock_client = AsyncMock()
    dummy_request = httpx.Request("POST", "https://api.meta.ai/v1/chat/completions")
    dummy_response = httpx.Response(
        429, request=dummy_request, text='{"error": "secret_internal_meta_quota"}'
    )
    rate_err = openai.RateLimitError(
        message="Rate limit exceeded",
        response=dummy_response,
        body={"error": "secret_internal_meta_quota"},
    )
    mock_client.chat.completions.create = AsyncMock(side_effect=rate_err)

    with patch("app.services.llm_service.get_llm_client", return_value=mock_client):
        with pytest.raises(RateLimitedError) as exc_info:
            await complete("system", "user")

    # Security check: Ensure no internal Meta details leak in error message
    assert "secret_internal_meta_quota" not in str(exc_info.value)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_instance, expected_exc",
    [
        (
            openai.APITimeoutError(
                request=httpx.Request("POST", "https://api.meta.ai/v1/chat/completions")
            ),
            MetaApiError,
        ),
        (
            openai.APIConnectionError(
                request=httpx.Request("POST", "https://api.meta.ai/v1/chat/completions")
            ),
            MetaApiError,
        ),
        (
            openai.APIStatusError(
                message="Internal Meta Server Error",
                response=httpx.Response(
                    500,
                    request=httpx.Request(
                        "POST", "https://api.meta.ai/v1/chat/completions"
                    ),
                    text="secret_500_leak",
                ),
                body=None,
            ),
            MetaApiError,
        ),
        (
            openai.OpenAIError("Generic SDK failure with secret_generic_leak"),
            MetaApiError,
        ),
    ],
)
async def test_complete_maps_api_errors(error_instance, expected_exc):
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=error_instance)

    with patch("app.services.llm_service.get_llm_client", return_value=mock_client):
        with pytest.raises(expected_exc) as exc_info:
            await complete("system", "user")

    # Security check: Ensure raw error strings are never leaked
    assert "secret_500_leak" not in str(exc_info.value)
    assert "secret_generic_leak" not in str(exc_info.value)
