"""Streaming tests for SarvamSTTProvider using a fake WebSocket server (no network)."""

import base64
import json

import pytest

from app.core.config import settings
from app.core.exceptions import MetaApiError
from app.providers.base import BaseSTTProvider, StreamEvent
from app.providers.stt.sarvam import SarvamSTTProvider


class FakeWS:
    """Scripted stand-in for a websockets connection."""

    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.sent: list[str] = []

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


def make_opener(script, captured):
    def opener(url, **kwargs):
        captured.append((url, kwargs))
        return FakeWS(script)

    return opener


async def two_chunks():
    yield b"\x00\x01" * 800
    yield b"\x02\x03" * 800


def test_partials_relayed_and_finals_joined(monkeypatch):
    monkeypatch.setattr(settings, "SARVAM_BASE_URL", "https://test.invalid")
    monkeypatch.setattr(settings, "SARVAM_VOICE_MODEL", "saaras:v4")
    script = [
        json.dumps({"event": "session.begin"}),
        json.dumps(
            {"event": "transcript.partial", "utterance_idx": 0, "text": "hello"}
        ),
        json.dumps(
            {"event": "transcript.final", "utterance_idx": 0, "text": "hello world"}
        ),
        json.dumps(
            {"event": "transcript.partial", "utterance_idx": 1, "text": "foo"}
        ),
        json.dumps(
            {"event": "transcript.final", "utterance_idx": 1, "text": "foo bar"}
        ),
        json.dumps({"event": "session.end"}),
    ]
    captured: list = []
    sent_holder: list = []

    class RecordingWS(FakeWS):
        async def __aexit__(self, *exc):
            sent_holder.extend(self.sent)
            return False

    def opener(url, **kwargs):
        captured.append((url, kwargs))
        return RecordingWS(script)

    provider = SarvamSTTProvider(ws_connect=opener)
    assert isinstance(provider, BaseSTTProvider)

    async def collect():
        return [e async for e in provider.stream_transcribe(two_chunks())]

    import asyncio

    events = asyncio.run(collect())

    partials = [e.text for e in events if e.kind == "partial"]
    finals = [e for e in events if e.kind == "final"]
    assert partials == ["hello", "foo"]
    assert len(finals) == 1
    assert finals[0].text == "hello world foo bar"
    assert all(isinstance(e, StreamEvent) for e in events)

    url, kwargs = captured[0]
    assert url.startswith("wss://test.invalid/speech-to-text-realtime/ws")
    assert "model=saaras:v4" in url
    assert "language_code=auto" in url  # no hint -> auto
    assert list(kwargs["additional_headers"]) == ["api-subscription-key"]

    frames = [json.loads(m) for m in sent_holder]
    assert frames[-1] == {"event": "end"}
    assert frames[0] == {
        "event": "audio_input",
        "audio": base64.b64encode(b"\x00\x01" * 800).decode(),
    }


def test_sent_frames_and_language_mapping(monkeypatch):
    monkeypatch.setattr(settings, "SARVAM_BASE_URL", "https://test.invalid")
    script = [json.dumps({"event": "session.end"})]
    sent_holder: list = []

    class RecordingWS(FakeWS):
        async def __aexit__(self, *exc):
            sent_holder.extend(self.sent)
            return False

    def opener(url, **kwargs):
        sent_holder.append(("URL", url))
        return RecordingWS(script)

    provider = SarvamSTTProvider(ws_connect=opener)

    async def collect():
        return [e async for e in provider.stream_transcribe(two_chunks(), ["Kannada"])]

    import asyncio

    events = asyncio.run(collect())
    assert events == [StreamEvent(kind="final", text="")]

    url = sent_holder[0][1]
    assert "language_code=kn-IN" in url
    frames = [json.loads(m) for m in sent_holder[1:]]
    assert frames[-1] == {"event": "end"}
    assert frames[0]["event"] == "audio_input"
    assert base64.b64decode(frames[0]["audio"]) == b"\x00\x01" * 800


def test_error_event_raises():
    script = [
        json.dumps({"event": "session.begin"}),
        json.dumps({"event": "error", "message": "boom"}),
    ]
    provider = SarvamSTTProvider(ws_connect=make_opener(script, []))

    async def collect():
        return [e async for e in provider.stream_transcribe(two_chunks())]

    import asyncio

    with pytest.raises(MetaApiError, match="boom"):
        asyncio.run(collect())


def test_connection_failure_raises_meta_error():
    def opener(url, **kwargs):
        raise ConnectionError("dial failed")

    provider = SarvamSTTProvider(ws_connect=opener)

    async def collect():
        return [e async for e in provider.stream_transcribe(two_chunks())]

    import asyncio

    with pytest.raises(MetaApiError, match="connection error"):
        asyncio.run(collect())
