"""Streaming tests for MetaSTTProvider using a fake WebSocket server."""

import json

import pytest

from app.core.config import settings
from app.core.exceptions import MetaApiError, RateLimitedError
from app.providers.base import BaseSTTProvider, StreamEvent
from app.providers.stt.meta import MetaSTTProvider

websockets = pytest.importorskip("websockets")
from websockets.exceptions import (  # noqa: E402
    ConnectionClosedError,
    ConnectionClosedOK,
)


class FakeNormalClose(ConnectionClosedOK):
    def __init__(self):
        pass  # provider never touches attrs on the OK path


class FakeRateLimited(ConnectionClosedError):
    def __init__(self):
        self.code = 1013


class FakeWS:
    """Scripted stand-in for a websockets connection."""

    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.sent: list = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, msg):
        self.sent.append(msg)

    async def recv(self):
        if not self.incoming:
            raise AssertionError("fake server ran out of scripted messages")
        msg = self.incoming.pop(0)
        if isinstance(msg, Exception):
            raise msg
        return msg


async def two_chunks():
    yield b"\x11\x22" * 1280  # 2560 bytes = 80 ms at 16 kHz
    yield b"\x33\x44" * 1280


def test_partials_then_single_final(monkeypatch):
    monkeypatch.setattr(settings, "META_BASE_URL", "https://test.invalid/v1")
    monkeypatch.setattr(settings, "META_API_KEY", "test-key")
    monkeypatch.setattr(
        settings, "DEFAULT_VOICE_MODEL", "muse-voice-transcribe-1.0"
    )
    script = [
        json.dumps({"sessionId": "sess-1"}),
        json.dumps(
            {
                "type": "transcript",
                "transcript": "how is",
                "final": False,
                "audioProcessedMs": 100,
            }
        ),
        json.dumps(
            {
                "type": "transcript",
                "transcript": "how is the weather",
                "final": True,
                "audioProcessedMs": 200,
            }
        ),
        FakeNormalClose(),
    ]
    captured: list = []
    sent_holder: list = []

    class RecordingWS(FakeWS):
        async def __aexit__(self, *exc):
            sent_holder.extend(self.sent)
            return False

    def opener(url):
        captured.append(url)
        return RecordingWS(script)

    provider = MetaSTTProvider(ws_connect=opener)
    assert isinstance(provider, BaseSTTProvider)

    async def collect():
        return [
            e
            async for e in provider.stream_transcribe(
                two_chunks(), ["English", "Hindi"]
            )
        ]

    import asyncio

    events = asyncio.run(collect())
    assert [e.kind for e in events] == ["partial", "final"]
    assert events[0] == StreamEvent(kind="partial", text="how is")
    assert events[1] == StreamEvent(kind="final", text="how is the weather")

    assert captured == ["wss://test.invalid/v1/asr/realtime"]
    handshake = json.loads(sent_holder[0])
    assert handshake["authorization"] == {"accessToken": "Bearer test-key"}
    assert handshake["audioEncoding"] == "PCM_16KHZ"
    assert handshake["model"] == "muse-voice-transcribe-1.0"
    assert handshake["mode"] == "PUSH_TO_TALK"
    assert handshake["languageBias"] == ["English", "Hindi"]
    # Raw binary audio frames, no base64/JSON envelope.
    assert sent_holder[1] == b"\x11\x22" * 1280
    assert sent_holder[2] == b"\x33\x44" * 1280
    assert json.loads(sent_holder[3]) == {"type": "endStream"}


def test_no_language_bias_omitted(monkeypatch):
    monkeypatch.setattr(settings, "META_BASE_URL", "https://test.invalid/v1")
    script = [json.dumps({"sessionId": "s"}), FakeNormalClose()]
    sent_holder: list = []

    class RecordingWS(FakeWS):
        async def __aexit__(self, *exc):
            sent_holder.extend(self.sent)
            return False

    provider = MetaSTTProvider(ws_connect=lambda url: RecordingWS(script))

    async def collect():
        return [e async for e in provider.stream_transcribe(two_chunks())]

    import asyncio

    events = asyncio.run(collect())
    assert events == [StreamEvent(kind="final", text="")]
    assert "languageBias" not in json.loads(sent_holder[0])


def test_error_event_raises():
    script = [
        json.dumps({"sessionId": "s"}),
        json.dumps({"type": "error", "message": "bad audio"}),
    ]
    provider = MetaSTTProvider(ws_connect=lambda url: FakeWS(script))

    async def collect():
        return [e async for e in provider.stream_transcribe(two_chunks())]

    import asyncio

    with pytest.raises(MetaApiError, match="bad audio"):
        asyncio.run(collect())


def test_rate_limit_close_maps_to_429():
    script = [json.dumps({"sessionId": "s"}), FakeRateLimited()]
    provider = MetaSTTProvider(ws_connect=lambda url: FakeWS(script))

    async def collect():
        return [e async for e in provider.stream_transcribe(two_chunks())]

    import asyncio

    with pytest.raises(RateLimitedError, match="rate limited"):
        asyncio.run(collect())
