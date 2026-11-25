"""
app/providers/stt/meta.py

Meta Muse Voice Transcribe STT provider.

Implements the BaseSTTProvider protocol by wrapping the existing
Meta ASR multipart REST endpoint. All logic is migrated verbatim from
app/services/stt_service.py so the stt_service thin wrapper can delegate
to this class without any behaviour change.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Optional

import httpx

from app.core.config import settings
from app.core.exceptions import InvalidAudioError, MetaApiError, RateLimitedError
from app.providers.base import StreamEvent
from app.services.meta_client import get_meta_client
from app.services.stt_service import TranscriptionResult


# Realtime spec (user-supplied Meta docs, 2026-11-25): wss://<base>/v1/asr
# /realtime. Auth lives in the first JSON frame:
# {"authorization": {"accessToken": "Bearer <MODEL_API_KEY>"}} (HTTP header
# and query-string key are ignored). Config is fixed per session: model,
# audioEncoding PCM_16KHZ (phone sends 16 kHz mono int16; server resamples),
# mode PUSH_TO_TALK, partialMode CUMULATIVE. Audio goes as raw binary frames
# (~80 ms), paced in real time: bursting >5 s ahead or stalling >10 s closes
# the socket with 1008 (pad silence on pauses). End: {"type": "endStream"}
# half-closes; server flushes, then closes with 1000 (no sessionEnd event).
# Server sends: {"sessionId": ...} ack (wait for it before audio),
# transcript {transcript, final, ...}, audioProgress, error {message, ...}.
# Limits: 256 concurrent streams/tenant, 16k starts/hour (close 1013).
_REALTIME_PATH = "/asr/realtime"
_STREAM_ENCODING = "PCM_16KHZ"
_STREAM_MODE = "PUSH_TO_TALK"


def _default_ws_connect(url: str, **kwargs):  # type: ignore[no-untyped-def]
    """Open a client WebSocket (lazy import so REST-only use stays light)."""
    try:
        import websockets
    except ImportError as exc:
        raise MetaApiError("Streaming needs the 'websockets' package") from exc
    return websockets.connect(url, **kwargs)


class MetaSTTProvider:
    """
    STT provider backed by Meta Muse Voice Transcribe API.

    Uses the shared httpx.AsyncClient from meta_client.py.
    Retries once on HTTP 500 with a 300 ms delay.
    """

    # Sample rate the phone streams at; the route uses this for its
    # end-of-stream duration/RMS checks. Handshake declares PCM_16KHZ.
    stream_sample_rate = 16000

    def __init__(self, ws_connect=None):  # type: ignore[no-untyped-def]
        """
        Args:
            ws_connect: Optional WebSocket opener for streaming tests.
                        Called as ws_connect(url) and must return an async
                        context manager yielding send()/recv() methods.
                        Defaults to websockets.connect.
        """
        self._ws_connect = ws_connect or _default_ws_connect

    async def transcribe(
        self,
        wav_bytes: bytes,
        languages: Optional[list[str]] = None,
    ) -> TranscriptionResult:
        """
        Transcribe WAV bytes using the Meta /asr/transcribe multipart endpoint.

        Args:
            wav_bytes: 16-bit PCM mono WAV bytes (16 or 24 kHz).
            languages: Optional language-bias hints (canonical Meta names).

        Returns:
            TranscriptionResult with transcript text and timing metrics.

        Raises:
            InvalidAudioError: HTTP 400 / 413 from Meta ASR.
            RateLimitedError: HTTP 429 from Meta ASR.
            MetaApiError: Network error or HTTP 500 (after one retry).
        """
        client = get_meta_client()
        endpoint = f"{str(client.base_url).rstrip('/')}/asr/transcribe"

        request_payload: dict = {
            "mode": "PUSH_TO_TALK",
            "model": settings.DEFAULT_VOICE_MODEL or "muse-voice-transcribe-1.0",
            "audioEncoding": "WAV",
        }
        if languages:
            request_payload["languageBias"] = list(languages)

        files = {
            "request": (None, json.dumps(request_payload), "application/json"),
            "audio": ("audio.wav", wav_bytes, "audio/wav"),
        }

        start_time = time.perf_counter()

        try:
            response = await client.post(endpoint, files=files)
            # Retry once on HTTP 500 with a short delay
            if response.status_code == 500:
                await asyncio.sleep(0.3)
                response = await client.post(endpoint, files=files)
        except httpx.HTTPError as exc:
            raise MetaApiError(f"Meta API connection error: {exc}") from None

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if response.status_code == 200:
            try:
                data = response.json()
            except Exception:
                raise MetaApiError(
                    "Failed to parse Meta API response", status_code=200
                )
            transcript = data.get("transcript", "")
            audio_duration_ms = data.get("audioDurationMs") or 0
            return TranscriptionResult(
                transcript=transcript,
                elapsed_ms=round(elapsed_ms, 2),
                audio_duration_ms=int(audio_duration_ms),
            )

        if response.status_code in (400, 413):
            raise InvalidAudioError("Invalid or unsupported audio payload")
        if response.status_code == 429:
            raise RateLimitedError("Meta API rate limit exceeded")
        if response.status_code == 500:
            raise MetaApiError("Meta API server error", status_code=500)

        raise MetaApiError(
            f"Meta API request failed with status {response.status_code}",
            status_code=response.status_code,
        )

    async def stream_transcribe(
        self,
        audio_chunks: AsyncIterator[bytes],
        languages: Optional[list[str]] = None,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream raw 16 kHz mono 16-bit PCM chunks to the Meta realtime
        WebSocket, yielding partials then the single final transcript.

        PUSH_TO_TALK: one cumulative partial stream, one final. Language
        hints pass through as-is (canonical Meta names, not BCP-47);
        omitted for automatic detection. No retry; idle waits use
        STREAM_IDLE_TIMEOUT_S. The caller must pace chunks in real time.

        Raises:
            InvalidAudioError: If the audio is rejected by the provider.
            RateLimitedError: On realtime 1013 rate-limit close.
            MetaApiError: Network error, idle timeout, or provider error.
        """
        try:
            from websockets.exceptions import (
                ConnectionClosedError,
                ConnectionClosedOK,
            )
        except ImportError as exc:
            raise MetaApiError(
                "Streaming needs the 'websockets' package"
            ) from exc

        api_key = settings.META_API_KEY or ""
        ws_base = (
            (settings.META_BASE_URL or "https://api.meta.ai/v1")
            .rstrip("/")
            .replace("https://", "wss://")
            .replace("http://", "ws://")
        )
        model = settings.DEFAULT_VOICE_MODEL or "muse-voice-transcribe-1.0"
        url = f"{ws_base}{_REALTIME_PATH}"

        handshake: dict = {
            "authorization": {"accessToken": f"Bearer {api_key}"},
            "audioEncoding": _STREAM_ENCODING,
            "model": model,
            "mode": _STREAM_MODE,
            "partialMode": "CUMULATIVE",
            "emitAudioProgress": True,
        }
        if languages:
            handshake["languageBias"] = list(languages)

        async def _send_all(ws, chunks) -> None:  # type: ignore[no-untyped-def]
            async for chunk in chunks:
                if chunk:
                    await ws.send(chunk)
            await ws.send(json.dumps({"type": "endStream"}))

        idle = settings.STREAM_IDLE_TIMEOUT_S
        try:
            async with self._ws_connect(url) as ws:
                await ws.send(json.dumps(handshake))
                try:
                    raw_ack = await asyncio.wait_for(ws.recv(), timeout=idle)
                except asyncio.TimeoutError as exc:
                    raise MetaApiError(
                        "Meta stream handshake timeout"
                    ) from exc
                try:
                    ack = json.loads(raw_ack)
                except ValueError as exc:
                    raise MetaApiError(
                        "Failed to parse Meta handshake"
                    ) from exc
                if not isinstance(ack, dict) or "sessionId" not in ack:
                    if isinstance(ack, dict) and ack.get("type") == "error":
                        raise MetaApiError(
                            f"Meta stream error: {ack.get('message', raw_ack)}"
                        )
                    raise MetaApiError("Meta stream handshake rejected")

                sender = asyncio.create_task(_send_all(ws, audio_chunks))
                final_text = ""
                try:
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=idle)
                        except asyncio.TimeoutError as exc:
                            raise MetaApiError(
                                "Meta stream idle timeout"
                            ) from exc
                        except ConnectionClosedOK:
                            break
                        except ConnectionClosedError as exc:
                            code = getattr(exc, "code", None)
                            if code == 1013:
                                raise RateLimitedError(
                                    "Meta realtime rate limited"
                                ) from exc
                            raise MetaApiError(
                                f"Meta stream closed: {code}"
                            ) from exc
                        try:
                            msg = json.loads(raw)
                        except ValueError as exc:
                            raise MetaApiError(
                                "Failed to parse Meta stream message"
                            ) from exc
                        event = msg.get("type", "")
                        if event == "transcript":
                            if msg.get("final"):
                                final_text = msg.get("transcript", "")
                            else:
                                yield StreamEvent(
                                    kind="partial",
                                    text=msg.get("transcript", ""),
                                )
                        elif event == "error":
                            raise MetaApiError(
                                f"Meta stream error: {msg.get('message', raw)}"
                            )
                        # Ignore audioProgress, speech*, speaker, unknown.
                finally:
                    if not sender.done():
                        sender.cancel()
                    try:
                        await sender
                    except asyncio.CancelledError:
                        pass
        except asyncio.CancelledError:
            raise
        except (MetaApiError, RateLimitedError):
            raise
        except Exception as exc:
            raise MetaApiError(
                f"Meta stream connection error: {exc}"
            ) from None

        yield StreamEvent(kind="final", text=final_text)

