"""WebSocket streaming speech endpoint: WS /v1/stream (Sarvam only for now)."""

from __future__ import annotations

import asyncio
import json
import math
import time
from array import array
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.config import settings
from app.core.exceptions import (
    InvalidAudioError,
    InvalidRequestError,
    MetaApiError,
    RateLimitedError,
)
from app.core.validators import (
    parse_languages,
    validate_context_text,
    validate_device_id,
)
from app.providers.factory import get_stt_provider
from app.schemas.process import ActionModel
from app.services import action_service

router = APIRouter()

HELLO_TIMEOUT_S = 10.0

# App-level close codes (4000-4999) mirroring the HTTP error contract.
_CODE_BAD_REQUEST = 4400
_CODE_TIMEOUT = 4408
_CODE_RATE_LIMITED = 4429
_CODE_UPSTREAM = 4502

# Phone audio is mono 16-bit PCM; the exact rate comes from the active
# provider (stream_sample_rate) so duration math stays correct per engine.
def _bytes_per_second(sample_rate: int) -> int:
    return sample_rate * 2


def _pcm_rms(pcm: bytes) -> float:
    """RMS amplitude of raw PCM, same subsampling as audio.validate_wav_bytes."""
    samples = array("h")
    samples.frombytes(pcm[: len(pcm) // 2 * 2])
    sub = samples[::10]
    if not sub:
        return 0.0
    return math.sqrt(sum(s * s for s in sub) / len(sub))


async def _send_error(websocket: WebSocket, code: int, detail: str) -> None:
    try:
        await websocket.send_json({"type": "error", "code": code, "detail": detail})
    except (RuntimeError, WebSocketDisconnect):
        pass


async def stream_endpoint(websocket: WebSocket) -> None:
    """Accept start -> forward audio -> relay partials -> final action."""
    await websocket.accept()
    started = time.perf_counter()
    state = {"chunks": 0, "bytes": 0}
    cut = {"at_max": False}
    forwarded = bytearray()

    # --- 1. Hello frame ----------------------------------------------------
    try:
        start = await asyncio.wait_for(
            websocket.receive_json(), timeout=HELLO_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        await _send_error(websocket, _CODE_TIMEOUT, "Timed out waiting for start")
        await websocket.close(code=_CODE_TIMEOUT)
        return
    except (ValueError, RuntimeError):
        await _send_error(websocket, _CODE_BAD_REQUEST, "Invalid start frame")
        await websocket.close(code=_CODE_BAD_REQUEST)
        return
    except WebSocketDisconnect:
        return

    if not isinstance(start, dict) or start.get("type") != "start":
        await _send_error(websocket, _CODE_BAD_REQUEST, "First frame must be start")
        await websocket.close(code=_CODE_BAD_REQUEST)
        return

    device_id = start.get("device_id")
    box_text = start.get("box_text") or ""
    languages_raw = start.get("languages")
    app_name = start.get("app")
    if not isinstance(box_text, str) or not isinstance(languages_raw, (str, type(None))):
        await _send_error(websocket, _CODE_BAD_REQUEST, "Invalid start fields")
        await websocket.close(code=_CODE_BAD_REQUEST)
        return

    try:
        validate_device_id(device_id)
        validate_context_text(box_text)
    except InvalidRequestError as exc:
        await _send_error(websocket, _CODE_BAD_REQUEST, str(exc))
        await websocket.close(code=_CODE_BAD_REQUEST)
        return
    parsed_langs = parse_languages(languages_raw)

    # --- 2. Provider --------------------------------------------------------
    provider = get_stt_provider()
    if not hasattr(provider, "stream_transcribe"):
        await _send_error(
            websocket, _CODE_UPSTREAM, "Active STT provider lacks streaming"
        )
        await websocket.close(code=_CODE_UPSTREAM)
        return
    sample_rate = getattr(provider, "stream_sample_rate", 16000) or 16000

    queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()

    async def read_phone() -> None:
        try:
            while True:
                message = await websocket.receive()
                if message.get("bytes") is not None:
                    if cut["at_max"]:
                        continue  # over limit: drop, keep draining phone
                    data = message["bytes"]
                    state["chunks"] += 1
                    state["bytes"] += len(data)
                    over_bytes = state["bytes"] > settings.STREAM_MAX_BYTES
                    over_time = (
                        time.perf_counter() - started
                    ) > settings.STREAM_MAX_SECONDS
                    if over_bytes or over_time:
                        # Cut at the max: stop forwarding, finalize what we
                        # have, keep draining the phone until end/disconnect.
                        cut["at_max"] = True
                        await queue.put(None)
                        continue
                    forwarded.extend(data)
                    await queue.put(data)
                elif message.get("text") is not None:
                    try:
                        frame = json.loads(message["text"])
                    except ValueError:
                        continue
                    if isinstance(frame, dict) and frame.get("type") == "end":
                        return
                    # Ignore unknown text frames.
        except WebSocketDisconnect:
            return
        finally:
            await queue.put(None)

    async def feed():  # type: ignore[no-untyped-def]
        while True:
            item = await queue.get()
            if item is None:
                return
            yield item

    reader = asyncio.create_task(read_phone())
    gen = provider.stream_transcribe(feed(), languages=parsed_langs)
    final_text = ""
    try:
        async for event in gen:
            if event.kind == "partial":
                try:
                    await websocket.send_json(
                        {"type": "partial", "text": event.text}
                    )
                except (RuntimeError, WebSocketDisconnect):
                    return
            else:
                final_text = event.text
    except RateLimitedError as exc:
        await _send_error(websocket, _CODE_RATE_LIMITED, str(exc) or "Rate limited")
        await websocket.close(code=_CODE_RATE_LIMITED)
        return
    except (InvalidAudioError, MetaApiError) as exc:
        await _send_error(websocket, _CODE_UPSTREAM, str(exc) or "Upstream error")
        await websocket.close(code=_CODE_UPSTREAM)
        return
    except WebSocketDisconnect:
        return
    finally:
        if not reader.done():
            reader.cancel()
        try:
            await gen.aclose()
        except Exception:  # noqa: BLE001, S110 -- best-effort cleanup
            pass

    # --- 3. End-of-stream guardrails (mirror /v1/process, skip the LLM) ----
    duration_s = len(forwarded) / _bytes_per_second(sample_rate)
    if duration_s < settings.MIN_AUDIO_DURATION_S:
        await _send_error(websocket, _CODE_BAD_REQUEST, "Audio too short")
        await websocket.close(code=_CODE_BAD_REQUEST)
        return
    if _pcm_rms(bytes(forwarded)) <= settings.SILENCE_RMS_THRESHOLD:
        await _send_error(websocket, _CODE_BAD_REQUEST, "Audio too quiet")
        await websocket.close(code=_CODE_BAD_REQUEST)
        return

    # --- 4. Same LLM step as POST /v1/process --------------------------------
    try:
        action_res = await action_service.process(
            final_text, box_text, app=app_name
        )
    except RateLimitedError as exc:
        await _send_error(websocket, _CODE_RATE_LIMITED, str(exc) or "Rate limited")
        await websocket.close(code=_CODE_RATE_LIMITED)
        return
    except MetaApiError as exc:
        await _send_error(websocket, _CODE_UPSTREAM, str(exc) or "Upstream error")
        await websocket.close(code=_CODE_UPSTREAM)
        return
    except WebSocketDisconnect:
        return

    action_model = None
    if action_res.action is not None:
        action_model = ActionModel(
            action=action_res.action.action,
            text=action_res.action.text,
            find=action_res.action.find,
            which=action_res.action.which,
        )

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    logger.info(
        "Stream timings for device {}: chunks={}, bytes={}, elapsed_ms={:.2f}, "
        "cut={}, action_type={}, used_fallback={}, fallback_reason={}, "
        "prompt_tokens={}, completion_tokens={}",
        device_id or "none",
        state["chunks"],
        state["bytes"],
        elapsed_ms,
        cut["at_max"],
        action_model.action if action_model else "none",
        action_res.used_fallback,
        action_res.fallback_reason or "none",
        action_res.prompt_tokens,
        action_res.completion_tokens,
    )

    try:
        await websocket.send_json(
            {
                "type": "final",
                "transcript": final_text,
                "action": action_model.model_dump() if action_model else None,
                "used_fallback": action_res.used_fallback,
                "note": action_res.fallback_reason,
                "cut": cut["at_max"],
            }
        )
    except (RuntimeError, WebSocketDisconnect):
        return
    await websocket.close()


router.websocket("/stream")(stream_endpoint)
