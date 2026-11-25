"""Live probe for the Sarvam real-time transcription WebSocket (UNVERIFIED).

Sends one WAV file to the candidate Sarvam streaming endpoint using your
SARVAM_API_KEY and prints the exact frames sent and messages received, so
the real protocol can be confirmed before building the streaming provider.

Nothing here is confirmed: the URL, query params, header name, frame
shape, and end event below are CANDIDATES from unverified notes. Every
value sent is printed; everything the server returns is printed verbatim
(including rejections -- a rejection message is itself useful data).

WARNING: output may contain your transcript text. Do not commit it.

Run (from Vboard_backend/):
    SARVAM_API_KEY=<key> .venv/Scripts/python.exe scripts/probe_sarvam_ws.py clip.wav
    SARVAM_API_KEY=<key> .venv/Scripts/python.exe scripts/probe_sarvam_ws.py clip.wav ^
        --url wss://api.sarvam.ai/speech-to-text-realtime/ws ^
        --model saaras:v4 --language-code kn-IN
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import wave

CHUNK_MS = 100  # candidate chunk size from notes


def read_pcm_chunks(path: str) -> tuple[dict, list[bytes]]:
    """Read WAV, require 16 kHz mono 16-bit PCM, split into ~100 ms chunks."""
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
    bytes_per_chunk = 16000 * 2 * CHUNK_MS // 1000
    chunks = [raw[i : i + bytes_per_chunk] for i in range(0, len(raw), bytes_per_chunk)]
    return props, chunks


async def probe(url: str, key: str, chunks: list[bytes]) -> None:
    try:
        import websockets  # noqa: PLC0415
    except ImportError:
        sys.exit("REFUSED: 'websockets' package not installed; cannot probe.")

    print(f"URL: {url}")
    print("HEADER NAMES SENT: ['api-subscription-key'] (value redacted)")
    print(f"CHUNKS: {len(chunks)} x ~{CHUNK_MS}ms, {sum(map(len, chunks))} bytes total")

    # CONFIRMED frame shapes (user-verified 2026-11-25, not from official docs):
    # audio chunks -> {"event": "audio_input", "audio": "<base64 linear16>"}
    # finish       -> {"event": "end"}
    # server sends -> transcript.partial, transcript.final, session.end, error
    audio_frames = [
        json.dumps({"event": "audio_input", "audio": base64.b64encode(c).decode()})
        for c in chunks
    ]
    end_frame = json.dumps({"event": "end"})

    try:
        async with websockets.connect(
            url,
            additional_headers={"api-subscription-key": key},
            max_size=None,
        ) as ws:
            print("CONNECTED: handshake accepted")
            for i, frame in enumerate(audio_frames):
                await ws.send(frame)
                if i == 0:
                    print(f"AUDIO FRAME[0] SENT (truncated): {frame[:120]}...")
            print(f"AUDIO FRAMES SENT: {len(audio_frames)}")
            await ws.send(end_frame)
            print(f"END FRAME SENT: {end_frame}")

            async def listen() -> None:
                try:
                    async for msg in ws:
                        print(f"RECEIVED: {msg}")
                except Exception as exc:  # noqa: BLE001 -- clean server close
                    print(f"CLOSED: {type(exc).__name__}: {exc}")

            try:
                await asyncio.wait_for(listen(), timeout=30.0)
            except asyncio.TimeoutError:
                print("TIMEOUT: no more messages within 30s after end frame")
    except Exception as exc:  # noqa: BLE001 -- probe must report, not raise
        print(f"FAILED: {type(exc).__name__}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Sarvam streaming STT.")
    parser.add_argument("wav", help="Path to 16 kHz mono 16-bit PCM WAV file")
    parser.add_argument(
        "--url",
        default="wss://api.sarvam.ai/speech-to-text-realtime/ws",
        help="Candidate WebSocket endpoint (unverified)",
    )
    parser.add_argument("--model", default="saaras:v4")
    parser.add_argument("--language-code", default="kn-IN")
    parser.add_argument("--stream-type", default="fast")
    parser.add_argument("--encoding", default="linear16")
    parser.add_argument("--sample-rate", default="16000")
    args = parser.parse_args()

    key = os.environ.get("SARVAM_API_KEY", "")
    if not key:
        sys.exit("REFUSED: set SARVAM_API_KEY in the environment (never on CLI).")

    # CONFIRMED query params (user-verified 2026-11-25): language_code,
    # model, stream_type, encoding, sample_rate. Key via header only.
    url = (
        f"{args.url}?model={args.model}&language_code={args.language_code}"
        f"&stream_type={args.stream_type}&encoding={args.encoding}"
        f"&sample_rate={args.sample_rate}"
    )

    props, chunks = read_pcm_chunks(args.wav)
    print(f"WAV: {props}")
    asyncio.run(probe(url, key, chunks))


if __name__ == "__main__":
    main()
