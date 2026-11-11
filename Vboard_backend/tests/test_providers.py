import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest

from app.core.config import settings
from app.core.exceptions import InvalidAudioError, MetaApiError, RateLimitedError
from app.providers.base import BaseLLMProvider, BaseSTTProvider
from app.providers.factory import get_llm_provider, get_stt_provider
from app.providers.llm.gemini import GoogleGeminiLLMProvider
from app.providers.llm.openai_compatible import OpenAICompatibleLLMProvider
from app.providers.stt.meta import MetaSTTProvider
from app.providers.stt.openai_whisper import OpenAIWhisperSTTProvider
from app.providers.stt.sarvam import SarvamSTTProvider
from app.schemas.actions import ACTION_RESPONSE_FORMAT
from app.services.llm_service import LLMResult
from app.services.stt_service import TranscriptionResult

# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "provider_name, expected_cls",
    [
        ("meta", MetaSTTProvider),
        (" META ", MetaSTTProvider),
        ("sarvam", SarvamSTTProvider),
        ("openai", OpenAIWhisperSTTProvider),
    ],
)
def test_get_stt_provider_selection(monkeypatch, provider_name, expected_cls):
    monkeypatch.setattr(settings, "STT_PROVIDER", provider_name)
    provider = get_stt_provider()
    assert isinstance(provider, expected_cls)
    assert isinstance(provider, BaseSTTProvider)


def test_get_stt_provider_invalid_raises(monkeypatch):
    monkeypatch.setattr(settings, "STT_PROVIDER", "unknown_stt")
    with pytest.raises(ValueError, match="Unknown STT_PROVIDER"):
        get_stt_provider()


def test_get_llm_provider_meta(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "meta")
    provider = get_llm_provider()
    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert isinstance(provider, BaseLLMProvider)
    assert provider._use_shared_meta_client is True
    assert provider._model == (settings.DEFAULT_LLM_MODEL or "muse-spark-1.3")


def test_get_llm_provider_openai(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "OPENAI_LLM_MODEL", "gpt-4o-mini")
    provider = get_llm_provider()
    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert provider._use_shared_meta_client is False
    assert provider._model == "gpt-4o-mini"
    assert provider._client_kwargs["api_key"] == "sk-test"


def test_get_llm_provider_groq(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk-test")
    provider = get_llm_provider()
    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert provider._use_shared_meta_client is False
    assert provider._model == settings.GROQ_LLM_MODEL
    assert provider._client_kwargs["base_url"] == settings.GROQ_BASE_URL


def test_get_llm_provider_google(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "google")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gem-test")
    provider = get_llm_provider()
    assert isinstance(provider, GoogleGeminiLLMProvider)
    assert isinstance(provider, BaseLLMProvider)
    assert provider._model == settings.GEMINI_LLM_MODEL


def test_get_llm_provider_invalid_raises(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "unknown_llm")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_llm_provider()


# ---------------------------------------------------------------------------
# SarvamSTTProvider tests
# ---------------------------------------------------------------------------


def _mock_httpx_async_client(response: httpx.Response | Exception):
    client = AsyncMock()
    if isinstance(response, Exception):
        client.post = AsyncMock(side_effect=response)
    else:
        client.post = AsyncMock(return_value=response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, client


@pytest.mark.asyncio
async def test_sarvam_stt_success_maps_bcp47_language(monkeypatch):
    monkeypatch.setattr(settings, "SARVAM_API_KEY", "sarvam-key")
    monkeypatch.setattr(settings, "SARVAM_BASE_URL", "https://api.sarvam.ai")
    monkeypatch.setattr(settings, "SARVAM_VOICE_MODEL", "saaras:v2")

    resp = httpx.Response(200, json={"transcript": "ನಮಸ್ಕಾರ"})
    cm, mock_client = _mock_httpx_async_client(resp)

    with patch(
        "app.providers.stt.sarvam.httpx.AsyncClient", return_value=cm
    ) as cls_mock:
        res = await SarvamSTTProvider().transcribe(
            b"wav_bytes", languages=["Kannada", "English"]
        )

    assert isinstance(res, TranscriptionResult)
    assert res.transcript == "ನಮಸ್ಕಾರ"
    assert res.audio_duration_ms == 0
    assert res.elapsed_ms >= 0

    cls_mock.assert_called_once()
    assert cls_mock.call_args.kwargs["headers"] == {
        "api-subscription-key": "sarvam-key"
    }
    post_args = mock_client.post.call_args
    assert post_args.args[0] == "https://api.sarvam.ai/speech-to-text"
    assert post_args.kwargs["data"] == {"model": "saaras:v2", "language_code": "kn-IN"}


@pytest.mark.asyncio
async def test_sarvam_stt_omits_unmapped_language(monkeypatch):
    monkeypatch.setattr(settings, "SARVAM_API_KEY", "sarvam-key")
    resp = httpx.Response(200, json={"transcript": "bonjour"})
    cm, mock_client = _mock_httpx_async_client(resp)

    with patch("app.providers.stt.sarvam.httpx.AsyncClient", return_value=cm):
        res = await SarvamSTTProvider().transcribe(b"wav_bytes", languages=["French"])

    assert res.transcript == "bonjour"
    assert "language_code" not in mock_client.post.call_args.kwargs["data"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code, expected_exc",
    [
        (400, InvalidAudioError),
        (413, InvalidAudioError),
        (429, RateLimitedError),
        (500, MetaApiError),
        (503, MetaApiError),
    ],
)
async def test_sarvam_stt_error_mapping(monkeypatch, status_code, expected_exc):
    monkeypatch.setattr(settings, "SARVAM_API_KEY", "sarvam-key")
    resp = httpx.Response(status_code, text="secret_sarvam_leak")
    cm, _ = _mock_httpx_async_client(resp)

    with patch("app.providers.stt.sarvam.httpx.AsyncClient", return_value=cm):
        with pytest.raises(expected_exc) as exc_info:
            await SarvamSTTProvider().transcribe(b"wav_bytes")

    assert "secret_sarvam_leak" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_sarvam_stt_network_error(monkeypatch):
    monkeypatch.setattr(settings, "SARVAM_API_KEY", "sarvam-key")
    cm, _ = _mock_httpx_async_client(httpx.ConnectTimeout("timed out"))

    with patch("app.providers.stt.sarvam.httpx.AsyncClient", return_value=cm):
        with pytest.raises(MetaApiError, match="Sarvam API connection error"):
            await SarvamSTTProvider().transcribe(b"wav_bytes")


# ---------------------------------------------------------------------------
# OpenAIWhisperSTTProvider tests
# ---------------------------------------------------------------------------


def _mock_openai_cm(mock_client: AsyncMock):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_openai_whisper_success_maps_iso639(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "OPENAI_BASE_URL", None)
    monkeypatch.setattr(settings, "OPENAI_VOICE_MODEL", "whisper-1")

    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(
        return_value=SimpleNamespace(text="नमस्ते")
    )

    with patch(
        "app.providers.stt.openai_whisper.openai.AsyncOpenAI",
        return_value=_mock_openai_cm(mock_client),
    ):
        res = await OpenAIWhisperSTTProvider().transcribe(
            b"wav_bytes", languages=["Hindi"]
        )

    assert res.transcript == "नमस्ते"
    assert res.audio_duration_ms == 0
    kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert kwargs["model"] == "whisper-1"
    assert kwargs["language"] == "hi"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_factory, expected_exc",
    [
        (
            lambda: openai.RateLimitError(
                "limit",
                response=httpx.Response(429, request=httpx.Request("POST", "https://x")),
                body=None,
            ),
            RateLimitedError,
        ),
        (
            lambda: openai.BadRequestError(
                "bad wav",
                response=httpx.Response(400, request=httpx.Request("POST", "https://x")),
                body=None,
            ),
            InvalidAudioError,
        ),
        (
            lambda: openai.APITimeoutError(
                request=httpx.Request("POST", "https://x")
            ),
            MetaApiError,
        ),
    ],
)
async def test_openai_whisper_error_mapping(monkeypatch, exc_factory, expected_exc):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")
    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(side_effect=exc_factory())

    with patch(
        "app.providers.stt.openai_whisper.openai.AsyncOpenAI",
        return_value=_mock_openai_cm(mock_client),
    ):
        with pytest.raises(expected_exc):
            await OpenAIWhisperSTTProvider().transcribe(b"wav_bytes")


# ---------------------------------------------------------------------------
# OpenAICompatibleLLMProvider tests (non-shared & fallback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_compatible_non_shared_client():
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Sunny today.")
                )
            ],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )
    )

    provider = OpenAICompatibleLLMProvider(
        api_key="sk-test",
        model="gpt-4o-mini",
        use_shared_meta_client=False,
    )

    with patch(
        "app.providers.llm.openai_compatible.openai.AsyncOpenAI",
        return_value=_mock_openai_cm(mock_client),
    ):
        res = await provider.complete(
            system_prompt="sys",
            user_text="weather?",
        )

    assert isinstance(res, LLMResult)
    assert res.text == "Sunny today."
    assert res.prompt_tokens == 10
    assert res.completion_tokens == 5
    sent_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert sent_kwargs["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_openai_compatible_shared_fallback_when_uninitialized():
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=None,
        )
    )

    provider = OpenAICompatibleLLMProvider(
        api_key="meta-key",
        model="muse-spark-1.3",
        base_url="https://api.meta.ai/v1",
        use_shared_meta_client=True,
    )

    with (
        patch(
            "app.providers.llm.openai_compatible.get_llm_client",
            side_effect=RuntimeError("not initialized"),
        ),
        patch(
            "app.providers.llm.openai_compatible.openai.AsyncOpenAI",
            return_value=_mock_openai_cm(mock_client),
        ),
    ):
        res = await provider.complete("sys", "usr")

    assert res.text == "ok"


# ---------------------------------------------------------------------------
# GoogleGeminiLLMProvider tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_complete_strips_additional_properties_and_parses():
    expected_json = '{"action":"insert","text":"hi","find":"","which":"last"}'
    gemini_payload = {
        "candidates": [{"content": {"parts": [{"text": expected_json}]}}],
        "usageMetadata": {"promptTokenCount": 30, "candidatesTokenCount": 12},
    }
    resp = httpx.Response(200, json=gemini_payload)
    cm, mock_client = _mock_httpx_async_client(resp)

    provider = GoogleGeminiLLMProvider(api_key="gem-key", model="gemini-2.5-flash")
    with patch("app.providers.llm.gemini.httpx.AsyncClient", return_value=cm):
        res = await provider.complete(
            system_prompt="sys prompt",
            user_text="hello",
            response_format=ACTION_RESPONSE_FORMAT,
        )

    assert res.text == '{"action":"insert","text":"hi","find":"","which":"last"}'
    assert res.prompt_tokens == 30
    assert res.completion_tokens == 12

    sent_url = mock_client.post.call_args.args[0]
    sent_body = mock_client.post.call_args.kwargs["json"]
    assert "models/gemini-2.5-flash:generateContent?key=gem-key" in sent_url
    assert sent_body["systemInstruction"] == {"parts": [{"text": "sys prompt"}]}
    assert sent_body["generationConfig"]["responseMimeType"] == "application/json"
    assert "additionalProperties" not in json.dumps(
        sent_body["generationConfig"]["responseSchema"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code, expected_exc",
    [
        (429, RateLimitedError),
        (500, MetaApiError),
        (503, MetaApiError),
        (400, MetaApiError),
    ],
)
async def test_gemini_error_mapping(status_code, expected_exc):
    resp = httpx.Response(status_code, text="secret_gemini_error")
    cm, _ = _mock_httpx_async_client(resp)

    provider = GoogleGeminiLLMProvider(api_key="gem-key", model="gemini-2.5-flash")
    with patch("app.providers.llm.gemini.httpx.AsyncClient", return_value=cm):
        with pytest.raises(expected_exc) as exc_info:
            await provider.complete("sys", "hi")

    assert "secret_gemini_error" not in str(exc_info.value)
