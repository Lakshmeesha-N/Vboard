import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.exceptions import InvalidAudioError, MetaApiError, RateLimitedError
from app.services.stt_service import TranscriptionResult, transcribe


@pytest.mark.asyncio
async def test_transcribe_language_bias_omitted_when_none():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.base_url = httpx.URL("https://api.meta.ai/v1")
    mock_resp = httpx.Response(
        200,
        json={"sessionId": "s1", "transcript": "ನಮಸ್ಕಾರ", "audioDurationMs": 1500},
    )
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.stt_service.get_meta_client", return_value=mock_client):
        res = await transcribe(b"fake_wav_bytes", languages=None)

    assert isinstance(res, TranscriptionResult)
    assert res.transcript == "ನಮಸ್ಕಾರ"
    assert res.audio_duration_ms == 1500
    assert res.elapsed_ms >= 0

    assert mock_client.post.call_count == 1
    call_kwargs = mock_client.post.call_args.kwargs
    files = call_kwargs["files"]
    req_json = json.loads(files["request"][1])
    assert "languageBias" not in req_json
    assert req_json["audioEncoding"] == "WAV"
    assert req_json["mode"] == "PUSH_TO_TALK"


@pytest.mark.asyncio
async def test_transcribe_language_bias_omitted_when_empty():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.base_url = httpx.URL("https://api.meta.ai/v1")
    mock_resp = httpx.Response(
        200,
        json={"transcript": "hello", "audioDurationMs": 1000},
    )
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.stt_service.get_meta_client", return_value=mock_client):
        res = await transcribe(b"fake_wav_bytes", languages=[])

    call_kwargs = mock_client.post.call_args.kwargs
    req_json = json.loads(call_kwargs["files"]["request"][1])
    assert "languageBias" not in req_json
    assert res.transcript == "hello"


@pytest.mark.asyncio
async def test_transcribe_language_bias_included_when_provided():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.base_url = httpx.URL("https://api.meta.ai/v1")
    mock_resp = httpx.Response(
        200,
        json={"transcript": "testing", "audioDurationMs": 2000},
    )
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.stt_service.get_meta_client", return_value=mock_client):
        await transcribe(b"fake_wav_bytes", languages=["Kannada", "English"])

    call_kwargs = mock_client.post.call_args.kwargs
    req_json = json.loads(call_kwargs["files"]["request"][1])
    assert "languageBias" in req_json
    assert req_json["languageBias"] == ["Kannada", "English"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_code, expected_exc",
    [
        (400, InvalidAudioError),
        (413, InvalidAudioError),
        (429, RateLimitedError),
    ],
)
async def test_transcribe_error_status_mapping(status_code, expected_exc):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.base_url = httpx.URL("https://api.meta.ai/v1")
    raw_leak_text = '{"secret_meta_leak": "raw_sensitive_server_details"}'
    mock_resp = httpx.Response(status_code, text=raw_leak_text)
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("app.services.stt_service.get_meta_client", return_value=mock_client):
        with pytest.raises(expected_exc) as exc_info:
            await transcribe(b"fake_wav_bytes")

    # Security check: Ensure raw response text never leaks into error message
    assert "raw_sensitive_server_details" not in str(exc_info.value)
    assert "secret_meta_leak" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_transcribe_retry_on_500_succeeds():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.base_url = httpx.URL("https://api.meta.ai/v1")
    err_resp = httpx.Response(500, text="Internal Server Error")
    ok_resp = httpx.Response(
        200,
        json={"transcript": "recovered", "audioDurationMs": 800},
    )
    mock_client.post = AsyncMock(side_effect=[err_resp, ok_resp])

    with patch("app.services.stt_service.get_meta_client", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            res = await transcribe(b"fake_wav_bytes")
            mock_sleep.assert_awaited_once_with(0.3)

    assert res.transcript == "recovered"
    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_transcribe_retry_on_500_fails_maps_to_meta_api_error():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.base_url = httpx.URL("https://api.meta.ai/v1")
    err_resp1 = httpx.Response(500, text="Internal Server Error 1")
    err_resp2 = httpx.Response(500, text="Internal Server Error 2")
    mock_client.post = AsyncMock(side_effect=[err_resp1, err_resp2])

    with patch("app.services.stt_service.get_meta_client", return_value=mock_client):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(MetaApiError) as exc_info:
                await transcribe(b"fake_wav_bytes")
            mock_sleep.assert_awaited_once_with(0.3)

    assert mock_client.post.call_count == 2
    assert "Internal Server Error" not in str(exc_info.value)
    assert exc_info.value.status_code == 500
