from unittest.mock import AsyncMock, patch

import httpx
import pytest
from loguru import logger

from app.core.config import settings
from app.core.exceptions import MetaApiError, RateLimitedError
from app.main import app
from app.services.stt_service import TranscriptionResult
from tests.test_audio import create_in_memory_wav


@pytest.fixture
def valid_16k_wav() -> bytes:
    return create_in_memory_wav(sample_rate=16000, duration_s=1.0)


@pytest.fixture
def valid_24k_wav() -> bytes:
    return create_in_memory_wav(sample_rate=24000, duration_s=1.0)


@pytest.mark.asyncio
async def test_process_valid_16k_success(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="Hello world",
        elapsed_ms=125.5,
        audio_duration_ms=1000,
    )

    with patch(
        "app.services.stt_service.transcribe", new=AsyncMock(return_value=mock_result)
    ) as mock_transcribe:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            resp = await client.post("/v1/process", files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == "Hello world"
    assert data["timing_ms"] >= 0
    assert data["audio_duration_ms"] == 1000
    mock_transcribe.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_valid_24k_success(valid_24k_wav):
    mock_result = TranscriptionResult(
        transcript="ನಮಸ್ಕಾರ",
        elapsed_ms=210.0,
        audio_duration_ms=1000,
    )

    with patch(
        "app.services.stt_service.transcribe", new=AsyncMock(return_value=mock_result)
    ) as mock_transcribe:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            files = {"audio": ("audio.wav", valid_24k_wav, "audio/wav")}
            resp = await client.post("/v1/process", files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert data["transcript"] == "ನಮಸ್ಕಾರ"
    assert data["timing_ms"] >= 0
    assert data["audio_duration_ms"] == 1000
    mock_transcribe.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_stream_upload_over_5mb_returns_413():
    # 5MB + 10 bytes payload
    oversized_bytes = b"RIFF" + b"\x00" * (settings.MAX_AUDIO_BYTES + 10)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"audio": ("audio.wav", oversized_bytes, "audio/wav")}
        resp = await client.post("/v1/process", files=files)

    assert resp.status_code == 413
    assert "exceeds maximum size" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_process_languages_trim_and_filter_empty(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="Test",
        elapsed_ms=100.0,
        audio_duration_ms=1000,
    )

    with patch(
        "app.services.stt_service.transcribe", new=AsyncMock(return_value=mock_result)
    ) as mock_transcribe:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            data = {"languages": " Kannada , , English "}
            resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200
    mock_transcribe.assert_awaited_once()
    _, kwargs = mock_transcribe.call_args
    assert kwargs["languages"] == ["Kannada", "English"]


@pytest.mark.asyncio
async def test_process_languages_unsupported_name_dropped(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="Test",
        elapsed_ms=100.0,
        audio_duration_ms=1000,
    )

    with patch(
        "app.services.stt_service.transcribe", new=AsyncMock(return_value=mock_result)
    ) as mock_transcribe:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            data = {"languages": "Kannada,Klingon,english"}
            resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200
    mock_transcribe.assert_awaited_once()
    _, kwargs = mock_transcribe.call_args
    # Klingon dropped, Kannada and English kept and canonicalized
    assert kwargs["languages"] == ["Kannada", "English"]


@pytest.mark.asyncio
async def test_process_languages_only_unknown_names_sends_none(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="Test",
        elapsed_ms=100.0,
        audio_duration_ms=1000,
    )

    with patch(
        "app.services.stt_service.transcribe", new=AsyncMock(return_value=mock_result)
    ) as mock_transcribe:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            data = {"languages": "Klingon,Elvish"}
            resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200
    mock_transcribe.assert_awaited_once()
    _, kwargs = mock_transcribe.call_args
    # All dropped, none remain -> languages=None
    assert kwargs["languages"] is None


@pytest.mark.asyncio
async def test_process_languages_exceeding_5_trimmed(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="Test",
        elapsed_ms=100.0,
        audio_duration_ms=1000,
    )

    with patch(
        "app.services.stt_service.transcribe", new=AsyncMock(return_value=mock_result)
    ) as mock_transcribe:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            data = {"languages": "Kannada,English,Hindi,Tamil,Telugu,Spanish"}
            resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200
    mock_transcribe.assert_awaited_once()
    _, kwargs = mock_transcribe.call_args
    assert kwargs["languages"] == ["Kannada", "English", "Hindi", "Tamil", "Telugu"]


@pytest.mark.asyncio
async def test_process_device_id_valid(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="Test",
        elapsed_ms=50.0,
        audio_duration_ms=1000,
    )

    with patch(
        "app.services.stt_service.transcribe", new=AsyncMock(return_value=mock_result)
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            data = {"device_id": "pixel-7_pro-01"}
            resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_process_device_id_invalid_chars_returns_400(valid_16k_wav):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
        data = {"device_id": "pixel-7!@#"}
        resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 400
    assert "invalid device_id" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_process_device_id_too_long_returns_400(valid_16k_wav):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
        data = {"device_id": "a" * 65}
        resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 400
    assert "invalid device_id" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_process_context_text_within_limit_accepted(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="Test",
        elapsed_ms=50.0,
        audio_duration_ms=1000,
    )

    with patch(
        "app.services.stt_service.transcribe", new=AsyncMock(return_value=mock_result)
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            data = {"context_text": "A" * 5000}
            resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_process_context_text_exceeding_10k_returns_400(valid_16k_wav):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
        data = {"context_text": "A" * 10001}
        resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 400
    assert "context_text exceeds maximum limit" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_process_privacy_caplog_never_logs_context_text_or_audio(
    valid_16k_wav, caplog
):
    # Hook loguru into pytest caplog handler
    handler_id = logger.add(caplog.handler, format="{message}")

    mock_result = TranscriptionResult(
        transcript="Secret decoded",
        elapsed_ms=50.0,
        audio_duration_ms=1000,
    )

    secret_context = "CONFIDENTIAL_USER_SCREEN_DATA_98765"
    valid_device_id = "trusted_device_007"

    try:
        with patch(
            "app.services.stt_service.transcribe",
            new=AsyncMock(return_value=mock_result),
        ):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
                data = {"context_text": secret_context, "device_id": valid_device_id}
                resp = await client.post("/v1/process", files=files, data=data)

        assert resp.status_code == 200

        # Privacy verifications:
        assert secret_context not in caplog.text
        assert "RIFF" not in caplog.text
        assert valid_device_id in caplog.text
    finally:
        logger.remove(handler_id)


@pytest.mark.asyncio
async def test_process_upstream_rate_limited_returns_429(valid_16k_wav):
    with patch(
        "app.services.stt_service.transcribe",
        new=AsyncMock(side_effect=RateLimitedError("Meta API rate limit exceeded")),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            resp = await client.post("/v1/process", files=files)

    assert resp.status_code == 429
    assert "rate limit" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_process_upstream_meta_connection_error_returns_502(valid_16k_wav):
    with patch(
        "app.services.stt_service.transcribe",
        new=AsyncMock(side_effect=MetaApiError("Meta API connection error")),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            resp = await client.post("/v1/process", files=files)

    assert resp.status_code == 502
    assert "service error" in resp.json()["detail"].lower()
