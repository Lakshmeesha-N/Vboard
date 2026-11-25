"""
app/providers/stt/sarvam.py

Sarvam AI (Saaras) STT provider.

Implements the BaseSTTProvider protocol by calling the Sarvam
speech-to-text REST endpoint, which excels at Indian-language audio.
Requires settings.SARVAM_API_KEY to be set.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from collections.abc import AsyncIterator
from typing import Optional

import httpx

from app.core.config import settings
from app.core.exceptions import InvalidAudioError, MetaApiError, RateLimitedError
from app.providers.base import StreamEvent
from app.services.stt_service import TranscriptionResult

# Mapping from canonical Meta language names to Sarvam BCP-47 codes.
# Only the 25 languages validated by app/core/validators.py are listed;
# unmapped languages are dropped rather than sent as-is.
_LANG_TO_BCP47: dict[str, str] = {
    "English": "en-IN",
    "Hindi": "hi-IN",
    "Bengali": "bn-IN",
    "Kannada": "kn-IN",
    "Malayalam": "ml-IN",
    "Marathi": "mr-IN",
    "Tamil": "ta-IN",
    "Telugu": "te-IN",
    "Gujarati": "gu-IN",
    "Odia": "od-IN",
    "Punjabi": "pa-IN",
    "Assamese": "as-IN",
    "Rajasthani": "raj-IN",
    "Sanskrit": "sa-IN",
    "Urdu": "ur-IN",
}


# Verified live 2026-11-25 via scripts/probe_sarvam_ws.py against
# wss://api.sarvam.ai/speech-to-text-realtime/ws (absent from official docs).
# Handshake: ?model=&language_code=&stream_type=fast&encoding=linear16
# &sample_rate=16000, header api-subscription-key (query-string key rejected).
# Audio frames: {"event": "audio_input", "audio": "<base64 linear16 16kHz>"}.
# Finish: {"event": "end"}. Server sends: session.begin, vad.speech_start /
# vad.speech_end, transcript.partial (cumulative text per utterance_idx),
# transcript.final (per utterance), session.end, error.
# Provider limits (user-verified, not in official docs): 20 concurrent
# streams on pay-as-you-go, 60 s idle timeout.
_STREAM_PATH = "/speech-to-text-realtime/ws"
_STREAM_TYPE = "fast"
_STREAM_ENCODING = "linear16"
_STREAM_SAMPLE_RATE = 16000


def _resolve_language_code(languages: Optional[list[str]]) -> Optional[str]:
    """Return the first mappable BCP-47 code, or None if unmapped."""
    if languages:
        for lang in languages:
            code = _LANG_TO_BCP47.get(lang)
            if code:
                return code
    return None


def _default_ws_connect(url: str, **kwargs):  # type: ignore[no-untyped-def]
    """Open a client WebSocket (lazy import so REST-only use stays light)."""
    try:
        import websockets
    except ImportError as exc:
        raise MetaApiError("Streaming needs the 'websockets' package") from exc
    return websockets.connect(url, **kwargs)


class SarvamSTTProvider:
    """
    STT provider backed by Sarvam AI Saaras speech-to-text API.

    Sends WAV bytes as multipart/form-data to the Sarvam ASR endpoint.
    Maps the first canonical language hint to a BCP-47 code when provided.
    Does NOT retry on 500 (Sarvam SLA is different from Meta's).
    """

    # Sample rate the phone streams at; the route uses this for its
    # end-of-stream duration/RMS checks.
    stream_sample_rate = 16000

    def __init__(self, ws_connect=None):  # type: ignore[no-untyped-def]
        """
        Args:
            ws_connect: Optional WebSocket opener for streaming tests.
                        Called as ws_connect(url, additional_headers=...,
                        max_size=...) and must return an async context
                        manager yielding send()/recv() methods. Defaults
                        to websockets.connect.
        """
        self._ws_connect = ws_connect or _default_ws_connect

    async def transcribe(
        self,
        wav_bytes: bytes,
        languages: Optional[list[str]] = None,
    ) -> TranscriptionResult:
        """
        Transcribe WAV bytes using the Sarvam speech-to-text API.

        Args:
            wav_bytes: 16-bit PCM mono WAV bytes.
            languages: Optional language-bias hints (canonical Meta names).
                       The first mappable language is used as language_code.

        Returns:
            TranscriptionResult with transcript text and timing metrics.

        Raises:
            InvalidAudioError: HTTP 400 / 413 from Sarvam.
            RateLimitedError: HTTP 429 from Sarvam.
            MetaApiError: Network error or HTTP 500.
        """
        api_key = settings.SARVAM_API_KEY or ""
        base_url = settings.SARVAM_BASE_URL.rstrip("/")
        model = settings.SARVAM_VOICE_MODEL

        headers = {"api-subscription-key": api_key}

        # Pick the first language that maps to a BCP-47 code
        language_code = _resolve_language_code(languages)

        data: dict = {"model": model}
        if language_code:
            data["language_code"] = language_code

        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}

        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(30.0, connect=5.0),
            ) as client:
                response = await client.post(
                    f"{base_url}/speech-to-text",
                    data=data,
                    files=files,
                )
        except httpx.HTTPError as exc:
            raise MetaApiError(f"Sarvam API connection error: {exc}") from None

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if response.status_code == 200:
            try:
                payload = response.json()
            except Exception:
                raise MetaApiError(
                    "Failed to parse Sarvam API response", status_code=200
                )
            transcript = payload.get("transcript", "")
            # Sarvam does not return audio duration; default to 0
            return TranscriptionResult(
                transcript=transcript,
                elapsed_ms=round(elapsed_ms, 2),
                audio_duration_ms=0,
            )

        if response.status_code in (400, 413):
            raise InvalidAudioError("Invalid or unsupported audio payload")
        if response.status_code == 429:
            raise RateLimitedError("Sarvam API rate limit exceeded")
        if response.status_code == 500:
            raise MetaApiError("Sarvam API server error", status_code=500)

        raise MetaApiError(
            f"Sarvam API request failed with status {response.status_code}",
            status_code=response.status_code,
        )

    async def stream_transcribe(
        self,
        audio_chunks: AsyncIterator[bytes],
        languages: Optional[list[str]] = None,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream raw 16 kHz mono 16-bit PCM chunks to the Sarvam realtime
        WebSocket, yielding partials then one joined final transcript.

        The final event joins per-utterance transcript.final texts in
        utterance_idx order with single spaces. Unmapped languages fall
        back to "auto" (the realtime endpoint supports it, unlike REST
        which drops them). No retry; idle waits use STREAM_IDLE_TIMEOUT_S.

        Raises:
            InvalidAudioError: If the audio is rejected by the provider.
            RateLimitedError: On HTTP 429 / quota exhausted.
            MetaApiError: Network error, idle timeout, or provider error.
        """
        api_key = settings.SARVAM_API_KEY or ""
        ws_base = (
            settings.SARVAM_BASE_URL.rstrip("/")
            .replace("https://", "wss://")
            .replace("http://", "ws://")
        )
        model = settings.SARVAM_VOICE_MODEL
        language_code = _resolve_language_code(languages) or "auto"
        url = (
            f"{ws_base}{_STREAM_PATH}?model={model}"
            f"&language_code={language_code}&stream_type={_STREAM_TYPE}"
            f"&encoding={_STREAM_ENCODING}&sample_rate={_STREAM_SAMPLE_RATE}"
        )

        async def _send_all(ws, chunks) -> None:  # type: ignore[no-untyped-def]
            async for chunk in chunks:
                if chunk:
                    await ws.send(
                        json.dumps(
                            {
                                "event": "audio_input",
                                "audio": base64.b64encode(chunk).decode(),
                            }
                        )
                    )
            await ws.send(json.dumps({"event": "end"}))

        finals: dict[int, str] = {}
        idle = settings.STREAM_IDLE_TIMEOUT_S
        try:
            async with self._ws_connect(
                url,
                additional_headers={"api-subscription-key": api_key},
                max_size=None,
            ) as ws:
                sender = asyncio.create_task(_send_all(ws, audio_chunks))
                try:
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=idle)
                        except asyncio.TimeoutError as exc:
                            raise MetaApiError(
                                "Sarvam stream idle timeout"
                            ) from exc
                        try:
                            msg = json.loads(raw)
                        except ValueError as exc:
                            raise MetaApiError(
                                "Failed to parse Sarvam stream message"
                            ) from exc
                        event = msg.get("event", "")
                        if event == "transcript.partial":
                            yield StreamEvent(
                                kind="partial", text=msg.get("text", "")
                            )
                        elif event == "transcript.final":
                            try:
                                idx = int(
                                    msg.get("utterance_idx", len(finals))
                                )
                            except (TypeError, ValueError):
                                idx = len(finals)
                            finals[idx] = msg.get("text", "")
                        elif event == "session.end":
                            break
                        elif event == "error":
                            raise MetaApiError(
                                f"Sarvam stream error: {msg.get('message', raw)}"
                            )
                        # Ignore session.begin, vad.*, and unknown events.
                finally:
                    if not sender.done():
                        sender.cancel()
                    try:
                        await sender
                    except asyncio.CancelledError:
                        pass
        except asyncio.CancelledError:
            raise
        except MetaApiError:
            raise
        except Exception as exc:
            raise MetaApiError(
                f"Sarvam stream connection error: {exc}"
            ) from None

        yield StreamEvent(
            kind="final",
            text=" ".join(finals[i] for i in sorted(finals)),
        )

