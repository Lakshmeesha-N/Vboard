"""Live probe for Meta's realtime transcription WebSocket.

Sends one 16 kHz mono 16-bit PCM WAV file, paced in real time (~80 ms
frames, monotonic clock: bursting >5 s ahead or stalling >10 s gets the
socket closed with 1008), and prints every frame sent and message received
verbatim. Key comes from META_API_KEY and is never printed.

Run (from Vboard_backend/):
    META_API_KEY=<key> .venv/Scripts/python.exe scripts/probe_meta_ws.py clip.wav
    META_API_KEY=<key> .venv/Scripts/python.exe scripts/probe_meta_ws.py clip.wav ^
        --language-bias English Hindi --keywords "Acme Mobile"

WARNING: output may contain your transcript text. Do not commit it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import wave

FRAME_MS = 80  # official example frame size


def read_pcm_chunks(path: str) -> tuple[dict, list[bytes]]:
    """Read WAV, require 16 kHz mono 16-bit PCM, split into ~80 ms frames."""
    with wave.open(path, "rb") as wf:
        props = {
            "channels": wf.getnchannels(),
            "sample_width": wf.getsampwidth(),
            "frame_rate": wf.getframerate(),
            "frames": wf.getnframes(),
        }
        if (
            props["channels"] != 1
            or props["sample_width"] != 2
            or props["frame_rate"] != 16000
        ):
            sys.exit(f"REFUSED: need 16 kHz mono 16-bit PCM, got {props}")
        raw = wf.readframes(props["frames"])
    stride = 16000 * 2 * FRAME_MS // 1000
    chunks = [raw[i : i + stride] for i in range(0, len(raw), stride)]
    return props, chunks


async def probe(url: str, key: str, model: str, biases: list[str],
                keywords: list[str], chunks: list[bytes]) -> None:
    try:
        import websockets
        from websockets.exceptions import (
            ConnectionClosedError,
            ConnectionClosedOK,
        )
    except ImportError:
        sys.exit("REFUSED: 'websockets' package not installed; cannot probe.")

    handshake = {
        "authorization": {"accessToken": f"Bearer {key[:4]}***REDACTED***"},
        "audioEncoding": "PCM_16KHZ",
        "model": model,
        "mode": "PUSH_TO_TALK",
        "partialMode": "CUMULATIVE",
        "emitAudioProgress": True,
    }
    if biases:
        handshake["languageBias"] = biases
    if keywords:
        handshake["keywords"] = keywords
    wire_handshake = dict(handshake)
    wire_handshake["authorization"] = {"accessToken": "Bearer ***REDACTED***"}

    print(f"URL: {url}")
    print(f"HANDSHAKE SENT: {json.dumps(wire_handshake)}")
    print(f"FRAMES: {len(chunks)} x ~{FRAME_MS}ms, {sum(map(len(chunks)))} bytes")

    try:
        async with websockets.connect(url) as ws:
            real_handshake = dict(handshake)
            real_handshake["authorization"] = {"accessToken": f"Bearer {key}"}
            await ws.send(json.dumps(real_handshake))
            ack = await asyncio.wait_for(ws.recv(), timeout=15.0)
            print(f"ACK: {ack}")

            # Paced sender: monotonic clock, real-time rate.
            async def send_paced() -> None:
                start = time.monotonic()
                for i, chunk in enumerate(chunks):
                    await ws.send(chunk)
                    target = start + (i + 1) * (FRAME_MS / 1000.0)
                    delay = target - time.monotonic()
                    if delay > 0:
                        await asyncio.sleep(delay)
                await ws.send(json.dumps({"type": "endStream"}))
                print("ENDSTREAM SENT")

            sender = asyncio.create_task(send_paced())
            try:
                async for msg in ws:
                    print(f"RECEIVED: {msg}")
            except ConnectionClosedOK as exc:
                print(f"CLOSED OK: code={exc.code}")
            except ConnectionClosedError as exc:
                print(f"CLOSED ERROR: code={exc.code} reason={exc.reason!r}")
            await sender
    except Exception as exc:  # noqa: BLE001 -- probe must report, not raise
        print(f"FAILED: {type(exc).__name__}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Meta realtime STT.")
    parser.add_argument("wav", help="Path to 16 kHz mono 16-bit PCM WAV file")
    parser.add_argument(
        "--url", default="wss://api.meta.ai/v1/asr/realtime",
    )
    parser.add_argument("--model", default="muse-voice-transcribe-1.0")
    parser.add_argument("--language-bias", nargs="*", default=[])
    parser.add_argument("--keywords", nargs="*", default=[])
    args = parser.parse_args()

    key = __import__("os").environ.get("META_API_KEY", "")
    if not key:
        sys.exit("REFUSED: set META_API_KEY in the environment (never on CLI).")

    props, chunks = read_pcm_chunks(args.wav)
    print(f"WAV: {props}")
    asyncio.run(probe(args.url, key, args.model, args.language_bias,
                      args.keywords, chunks))


if __name__ == "__main__":
    main()
