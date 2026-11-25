"""WebSocket route tests for WS /v1/stream (fake provider, no network)."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.providers.base import StreamEvent
from app.services.action_service import Action, ActionResult

# 1600 bytes = 50 ms of 16 kHz mono 16-bit PCM. Twelve chunks = 0.6 s.
LOUD_CHUNK = b"\x01\x02" * 800
SILENT_CHUNK = b"\x00" * 1600


class FakeStreamProvider:
    def __init__(self):
        self.received_chunks: list[bytes] = []
        self.received_languages = None

    async def stream_transcribe(self, audio_chunks, languages=None):
        self.received_languages = languages
        async for chunk in audio_chunks:
            self.received_chunks.append(chunk)
        yield StreamEvent(kind="partial", text="hel")
        yield StreamEvent(kind="final", text="hello")


def make_action_result():
    return ActionResult(
        action=Action(action="insert", text="hello", find="", which="last"),
        used_fallback=False,
        fallback_reason=None,
        elapsed_ms=10.0,
        prompt_tokens=20,
        completion_tokens=10,
        cached_tokens=0,
        reasoning_tokens=0,
    )


def run_stream(messages):
    """Drive one WS session; return received frames and the provider."""
    provider = FakeStreamProvider()
    received = []
    with (
        patch("app.api.v1.stream.get_stt_provider", return_value=provider),
        patch(
            "app.services.action_service.process",
            new=AsyncMock(return_value=make_action_result()),
        ),
    ):
        client = TestClient(app)
        with client.websocket_connect("/v1/stream") as ws:
            for msg in messages:
                if isinstance(msg, bytes):
                    ws.send_bytes(msg)
                else:
                    ws.send_json(msg)
            while True:
                try:
                    frame = ws.receive_json()
                except Exception:  # noqa: BLE001 -- server closed
                    break
                received.append(frame)
                if frame["type"] in ("final", "error"):
                    break
    return received, provider


def start_frame(**overrides):
    frame = {
        "type": "start",
        "device_id": "test-device-1",
        "languages": "Kannada",
        "box_text": "old text",
        "app": "Gmail",
    }
    frame.update(overrides)
    return frame


def test_stream_happy_path():
    received, provider = run_stream(
        [start_frame()] + [LOUD_CHUNK] * 12 + [{"type": "end"}]
    )
    assert received[0] == {"type": "partial", "text": "hel"}
    final = received[-1]
    assert final["type"] == "final"
    assert final["transcript"] == "hello"
    assert final["action"]["action"] == "insert"
    assert final["used_fallback"] is False
    assert final["cut"] is False
    assert provider.received_chunks == [LOUD_CHUNK] * 12
    assert provider.received_languages == ["Kannada"]


def test_stream_rejects_non_start_first_frame():
    received, _ = run_stream([{"type": "hello"}])
    assert received[-1]["type"] == "error"
    assert received[-1]["code"] == 4400


def test_stream_unsupported_provider():
    with patch("app.api.v1.stream.get_stt_provider", return_value=object()):
        client = TestClient(app)
        with client.websocket_connect("/v1/stream") as ws:
            ws.send_json({"type": "start", "device_id": "d1"})
            err = ws.receive_json()
            assert err["type"] == "error"
            assert err["code"] == 4502


def test_stream_cuts_at_max_and_finalizes(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "STREAM_MAX_BYTES", 16000)
    received, provider = run_stream(
        [start_frame()] + [LOUD_CHUNK] * 14 + [{"type": "end"}]
    )
    final = received[-1]
    assert final["type"] == "final"
    assert final["cut"] is True
    # Only the first 0.5 s was forwarded; the rest was dropped.
    assert provider.received_chunks == [LOUD_CHUNK] * 10


def test_stream_rejects_too_short_audio():
    received, _ = run_stream([start_frame(), {"type": "end"}])
    assert received[-1]["type"] == "error"
    assert received[-1]["code"] == 4400


def test_stream_rejects_silent_audio():
    received, _ = run_stream(
        [start_frame()] + [SILENT_CHUNK] * 12 + [{"type": "end"}]
    )
    assert received[-1]["type"] == "error"
    assert received[-1]["code"] == 4400
