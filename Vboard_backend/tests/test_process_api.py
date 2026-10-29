from unittest.mock import AsyncMock, patch

import httpx
import pytest
from loguru import logger

from app.core.config import settings
from app.core.exceptions import MetaApiError, RateLimitedError
from app.main import app
from app.services.action_service import Action, ActionResult
from app.services.stt_service import TranscriptionResult
from tests.test_audio import create_in_memory_wav


@pytest.fixture
def valid_16k_wav() -> bytes:
    return create_in_memory_wav(sample_rate=16000, duration_s=1.0)


@pytest.fixture
def valid_24k_wav() -> bytes:
    return create_in_memory_wav(sample_rate=24000, duration_s=1.0)


@pytest.fixture(autouse=True)
def mock_default_action():
    default_res = ActionResult(
        action=Action(action="insert", text="default text", find="", which="last"),
        used_fallback=False,
        fallback_reason=None,
        elapsed_ms=10.0,
        prompt_tokens=20,
        completion_tokens=10,
        cached_tokens=0,
        reasoning_tokens=0,
    )
    with patch(
        "app.services.action_service.process",
        new=AsyncMock(return_value=default_res),
    ) as m:
        yield m


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
    assert data["action"] == {
        "action": "insert",
        "text": "default text",
        "find": "",
        "which": "last",
    }
    assert data["used_fallback"] is False
    assert data["note"] is None
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
        transcript="test",
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
            data = {"languages": "  Kannada  , , English  "}
            resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200
    mock_transcribe.assert_awaited_once()
    _, kwargs = mock_transcribe.call_args
    assert kwargs["languages"] == ["Kannada", "English"]


@pytest.mark.asyncio
async def test_process_languages_unsupported_name_dropped(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="test",
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
            data = {"languages": "Kannada, Klingon, English"}
            resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200
    mock_transcribe.assert_awaited_once()
    _, kwargs = mock_transcribe.call_args
    assert kwargs["languages"] == ["Kannada", "English"]


@pytest.mark.asyncio
async def test_process_languages_only_unknown_names_sends_none(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="test",
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
            data = {"languages": "Elvish, Klingon"}
            resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200
    mock_transcribe.assert_awaited_once()
    _, kwargs = mock_transcribe.call_args
    assert kwargs["languages"] is None


@pytest.mark.asyncio
async def test_process_languages_exceeding_5_trimmed(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="test",
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
            data = {"languages": "Kannada, Hindi, English, Tamil, Telugu, Bengali"}
            resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200
    mock_transcribe.assert_awaited_once()
    _, kwargs = mock_transcribe.call_args
    assert len(kwargs["languages"]) == 5
    assert kwargs["languages"] == ["Kannada", "Hindi", "English", "Tamil", "Telugu"]


@pytest.mark.asyncio
async def test_process_device_id_valid(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="test",
        elapsed_ms=100.0,
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
            data = {"device_id": "device_123-abc_XYZ"}
            resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_process_device_id_invalid_chars_returns_400(valid_16k_wav):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
        data = {"device_id": "device!@#$"}
        resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 400
    assert "device_id" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_process_device_id_too_long_returns_400(valid_16k_wav):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
        data = {"device_id": "a" * 65}
        resp = await client.post("/v1/process", files=files, data=data)

    assert resp.status_code == 400
    assert "device_id" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_process_context_text_within_limit_accepted(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="test",
        elapsed_ms=100.0,
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
            data = {"context_text": "A" * 10000}
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


@pytest.mark.asyncio
async def test_process_unhandled_exception_returns_500(valid_16k_wav, caplog):
    handler_id = logger.add(caplog.handler, format="{message}")

    try:
        with patch(
            "app.services.pipeline.run",
            new=AsyncMock(side_effect=RuntimeError("Unexpected pipeline failure")),
        ):
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
                resp = await client.post("/v1/process", files=files)

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal server error"
        assert "Unhandled error: RuntimeError" in caplog.text
        assert "Unexpected pipeline failure" not in caplog.text
    finally:
        logger.remove(handler_id)


@pytest.mark.asyncio
async def test_process_timings_included_when_debug_true(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="Debug check",
        elapsed_ms=50.0,
        audio_duration_ms=1000,
    )

    with patch("app.core.config.settings.DEBUG", True):
        with patch(
            "app.services.stt_service.transcribe",
            new=AsyncMock(return_value=mock_result),
        ):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
                resp = await client.post("/v1/process", files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert "timings_ms" in data
    assert data["timings_ms"] is not None
    assert "read_ms" in data["timings_ms"]
    assert "guardrail_ms" in data["timings_ms"]
    assert "stt_ms" in data["timings_ms"]
    assert "spark_ms" in data["timings_ms"]
    assert "total_ms" in data["timings_ms"]
    assert (
        data["timings_ms"]["total_ms"]
        >= round(
            data["timings_ms"]["guardrail_ms"]
            + data["timings_ms"]["stt_ms"]
            + data["timings_ms"]["spark_ms"],
            2,
        )
        - 0.01
    )


@pytest.mark.asyncio
async def test_process_timings_omitted_when_debug_false(valid_16k_wav):
    mock_result = TranscriptionResult(
        transcript="Debug check",
        elapsed_ms=50.0,
        audio_duration_ms=1000,
    )

    with patch("app.core.config.settings.DEBUG", False):
        with patch(
            "app.services.stt_service.transcribe",
            new=AsyncMock(return_value=mock_result),
        ):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
                resp = await client.post("/v1/process", files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("timings_ms") is None


# ---- New Spark Wire Tests ----


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action_type, action_text, action_find",
    [
        ("insert", "new text", ""),
        ("replace", "replacement text", "target word"),
        ("rewrite", "full rewritten box text", ""),
    ],
)
async def test_process_actions_insert_replace_rewrite(
    valid_16k_wav, action_type, action_text, action_find
):
    mock_stt = TranscriptionResult(
        transcript="sample speech", elapsed_ms=80.0, audio_duration_ms=1000
    )
    mock_act = ActionResult(
        action=Action(
            action=action_type, text=action_text, find=action_find, which="last"
        ),
        used_fallback=False,
        fallback_reason=None,
        elapsed_ms=30.0,
        prompt_tokens=25,
        completion_tokens=10,
        cached_tokens=0,
        reasoning_tokens=0,
    )

    with (
        patch(
            "app.services.stt_service.transcribe",
            new=AsyncMock(return_value=mock_stt),
        ),
        patch(
            "app.services.action_service.process",
            new=AsyncMock(return_value=mock_act),
        ),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            resp = await c.post("/v1/process", files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] == {
        "action": action_type,
        "text": action_text,
        "find": action_find,
        "which": "last",
    }
    assert data["used_fallback"] is False
    assert data["note"] is None


@pytest.mark.asyncio
async def test_process_spark_fallback_gives_http_200_with_insert_and_note(
    valid_16k_wav,
):
    mock_stt = TranscriptionResult(
        transcript="raw transcript text", elapsed_ms=80.0, audio_duration_ms=1000
    )
    mock_act = ActionResult(
        action=Action(
            action="insert", text="raw transcript text", find="", which="last"
        ),
        used_fallback=True,
        fallback_reason="spark_error",
        elapsed_ms=0.0,
        prompt_tokens=0,
        completion_tokens=0,
        cached_tokens=0,
        reasoning_tokens=0,
    )

    with (
        patch(
            "app.services.stt_service.transcribe",
            new=AsyncMock(return_value=mock_stt),
        ),
        patch(
            "app.services.action_service.process",
            new=AsyncMock(return_value=mock_act),
        ),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            resp = await c.post("/v1/process", files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert data["used_fallback"] is True
    assert data["note"] == "spark_error"
    assert data["action"] == {
        "action": "insert",
        "text": "raw transcript text",
        "find": "",
        "which": "last",
    }


@pytest.mark.asyncio
async def test_process_find_not_found_gives_null_action_and_note(valid_16k_wav):
    mock_stt = TranscriptionResult(
        transcript="replace unknown", elapsed_ms=80.0, audio_duration_ms=1000
    )
    mock_act = ActionResult(
        action=None,
        used_fallback=True,
        fallback_reason="find_not_found",
        elapsed_ms=50.0,
        prompt_tokens=20,
        completion_tokens=10,
        cached_tokens=0,
        reasoning_tokens=0,
    )

    with (
        patch(
            "app.services.stt_service.transcribe",
            new=AsyncMock(return_value=mock_stt),
        ),
        patch(
            "app.services.action_service.process",
            new=AsyncMock(return_value=mock_act),
        ),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            resp = await c.post("/v1/process", files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] is None
    assert data["used_fallback"] is True
    assert data["note"] == "find_not_found"


@pytest.mark.asyncio
async def test_process_empty_speech_gives_null_action(valid_16k_wav):
    mock_stt = TranscriptionResult(
        transcript="", elapsed_ms=80.0, audio_duration_ms=1000
    )
    mock_act = ActionResult(
        action=None,
        used_fallback=False,
        fallback_reason="empty_speech",
        elapsed_ms=0.0,
        prompt_tokens=0,
        completion_tokens=0,
        cached_tokens=0,
        reasoning_tokens=0,
    )

    with (
        patch(
            "app.services.stt_service.transcribe",
            new=AsyncMock(return_value=mock_stt),
        ),
        patch(
            "app.services.action_service.process",
            new=AsyncMock(return_value=mock_act),
        ),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            resp = await c.post("/v1/process", files=files)

    assert resp.status_code == 200
    data = resp.json()
    assert data["action"] is None
    assert data["used_fallback"] is False
    assert data["note"] == "empty_speech"


@pytest.mark.asyncio
async def test_process_context_text_reaches_action_service_and_not_logged(
    valid_16k_wav, caplog
):
    handler_id = logger.add(caplog.handler, format="{message}")
    secret_box_context = "SECRET_BOX_NEVER_LOGGED_999"

    mock_stt = TranscriptionResult(
        transcript="voice words", elapsed_ms=80.0, audio_duration_ms=1000
    )
    mock_act = ActionResult(
        action=Action(action="insert", text="voice words", find="", which="last"),
        used_fallback=False,
        fallback_reason=None,
        elapsed_ms=20.0,
        prompt_tokens=10,
        completion_tokens=5,
        cached_tokens=0,
        reasoning_tokens=0,
    )

    try:
        with (
            patch(
                "app.services.stt_service.transcribe",
                new=AsyncMock(return_value=mock_stt),
            ),
            patch(
                "app.services.action_service.process",
                new=AsyncMock(return_value=mock_act),
            ) as mock_action_process,
        ):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as c:
                files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
                data = {"context_text": secret_box_context}
                resp = await c.post("/v1/process", files=files, data=data)

        assert resp.status_code == 200
        mock_action_process.assert_awaited_once_with("voice words", secret_box_context)
        assert secret_box_context not in caplog.text
        assert "spark_ms=" in caplog.text
    finally:
        logger.remove(handler_id)


@pytest.mark.asyncio
async def test_process_muse_error_does_not_call_spark(valid_16k_wav):
    mock_action_process = AsyncMock()

    with (
        patch(
            "app.services.stt_service.transcribe",
            new=AsyncMock(side_effect=RateLimitedError("Meta API rate limit exceeded")),
        ),
        patch("app.services.action_service.process", mock_action_process),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            files = {"audio": ("audio.wav", valid_16k_wav, "audio/wav")}
            resp = await c.post("/v1/process", files=files)

    assert resp.status_code == 429
    mock_action_process.assert_not_called()
