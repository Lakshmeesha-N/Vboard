import argparse
import io
import sys
import threading
import time
import wave
from typing import Any, Optional

import httpx

ALLOWED_RATES = (16000, 24000)

# Non-typing keys safe for hold-to-record in a terminal.
# Modifier keys (ctrl, shift, alt) and special keys — never type characters.
_MODIFIER_KEYS = {
    "ctrl",
    "ctrl_l",
    "ctrl_r",
    "shift",
    "shift_l",
    "shift_r",
    "alt",
    "alt_l",
    "alt_r",
    "scroll_lock",
    "pause",
}


def parse_key(raw: str) -> tuple[str, ...]:
    """
    Parse --key into a tuple of key names.

    Accepted formats (case-insensitive):
      ctrl_r              -> single modifier key (default: Right Ctrl)
      shift_r             -> single modifier key (Right Shift)
      ctrl+shift          -> combo of two modifier keys
      scroll_lock / pause -> non-character special keys

    Returns a tuple of one or two lowercased key name strings.
    Raises ValueError with a clear message on invalid input.
    """
    raw = raw.strip().lower()
    parts = [p.strip() for p in raw.split("+")]
    if not parts or any(not p for p in parts):
        raise ValueError("Key cannot be empty.")
    for p in parts:
        if p not in _MODIFIER_KEYS:
            valid = ", ".join(sorted(_MODIFIER_KEYS))
            raise ValueError(
                f"Key '{p}' is not supported. Choose from: {valid}\n"
                "Do NOT use letter keys or function keys — "
                "they type into or interfere with the terminal/system."
            )
    if len(parts) > 2:
        raise ValueError("Maximum two keys in a combo (e.g. ctrl+shift).")
    return tuple(parts)


def resolve_pynput_keys(
    key_tuple: tuple[str, ...], keyboard_module: Any
) -> list[set[Any]]:
    """
    Map parsed key names to sets of pynput.keyboard.Key objects.
    Each element in the returned list corresponds to a required slot in a combo.
    """
    key_cls = keyboard_module.Key
    mapping = {
        "ctrl": {key_cls.ctrl, key_cls.ctrl_l, key_cls.ctrl_r},
        "ctrl_l": {key_cls.ctrl_l, key_cls.ctrl},
        "ctrl_r": {key_cls.ctrl_r},
        "shift": {key_cls.shift, key_cls.shift_r},
        "shift_l": {key_cls.shift},
        "shift_r": {key_cls.shift_r},
        "alt": {
            key_cls.alt,
            key_cls.alt_l,
            key_cls.alt_gr,
            getattr(key_cls, "alt_r", key_cls.alt_gr),
        },
        "alt_l": {key_cls.alt_l, key_cls.alt},
        "alt_r": {key_cls.alt_gr, getattr(key_cls, "alt_r", key_cls.alt_gr)},
        "scroll_lock": {key_cls.scroll_lock},
        "pause": {key_cls.pause},
    }
    slots = []
    for k in key_tuple:
        target_keys = mapping.get(k)
        if not target_keys:
            raise ValueError(f"Unknown key '{k}'")
        slots.append({target for target in target_keys if target is not None})
    return slots


def apply_action(box: str, action: Optional[dict[str, Any]]) -> str:
    """
    Apply a parsed action dictionary to the in-memory box string.

    Pure function with no external I/O or state modification.
    """
    if not action or not isinstance(action, dict):
        return box

    act_type = action.get("action")
    text = action.get("text", "")
    find = action.get("find", "")
    which = str(action.get("which", "last")).strip().lower()

    if act_type == "insert":
        if not text:
            return box
        if not box:
            return text
        if box.endswith(" ") or box.endswith("\n"):
            return box + text
        return box + " " + text

    if act_type == "rewrite":
        return text

    if act_type == "replace":
        if not find:
            return box

        # Match occurrences case-insensitively or exact match
        # Let's find occurrences of `find` in `box`
        # We first check exact matches; if none, check case-insensitive matches
        target = find
        indices = []
        start = 0
        while True:
            idx = box.find(target, start)
            if idx == -1:
                break
            indices.append((idx, idx + len(target)))
            start = idx + len(target)

        if not indices:
            # Try case-insensitive search
            lower_box = box.lower()
            lower_target = target.lower()
            start = 0
            while True:
                idx = lower_box.find(lower_target, start)
                if idx == -1:
                    break
                indices.append((idx, idx + len(lower_target)))
                start = idx + len(lower_target)

        if not indices:
            return box

        # Determine which occurrence to replace
        if which == "all":
            # Replace all occurrences from right to left to keep indices valid
            res = box
            for start_idx, end_idx in reversed(indices):
                res = res[:start_idx] + text + res[end_idx:]
            return res

        chosen_idx = -1
        if which == "first":
            chosen_idx = 0
        elif which == "last":
            chosen_idx = len(indices) - 1
        elif which.isdigit():
            # 1-based index support
            pos = int(which)
            if 1 <= pos <= len(indices):
                chosen_idx = pos - 1
            else:
                return box
        else:
            # Default to last if unrecognized
            chosen_idx = len(indices) - 1

        start_idx, end_idx = indices[chosen_idx]
        return box[:start_idx] + text + box[end_idx:]

    return box


def build_wav_in_memory(raw_pcm: bytes, sample_rate: int) -> bytes:
    """Encode raw 16-bit mono PCM bytes into an in-memory WAV byte string."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(raw_pcm)
    return buf.getvalue()


class VoiceTestApp:
    def __init__(
        self,
        url: str,
        sample_rate: int,
        key_display: str,
        languages: Optional[list[str]] = None,
    ):
        self.url = url.rstrip("/")
        self.sample_rate = sample_rate
        self.key_display = key_display
        self.languages = languages or []

        self.box: str = ""
        self.undo_stack: list[str] = []

        self.is_recording = False
        self.audio_chunks: list[bytes] = []
        self.record_start_time: float = 0.0
        self.stream = None
        self.lock = threading.Lock()
        self.running = True

    def _audio_callback(self, indata, frames, time_info, status):
        """sounddevice callback for incoming audio chunks."""
        with self.lock:
            if self.is_recording:
                # indata is cffi raw buffer or numpy array depending on stream
                self.audio_chunks.append(bytes(indata))

    def start_recording(self):
        with self.lock:
            if self.is_recording:
                return
            self.is_recording = True
            self.audio_chunks = []
            self.record_start_time = time.perf_counter()
            print(f"\n[Recording started... Hold {self.key_display} and speak]")

    def stop_and_send(self):
        with self.lock:
            if not self.is_recording:
                return
            self.is_recording = False
            duration = time.perf_counter() - self.record_start_time
            raw_pcm = b"".join(self.audio_chunks)
            self.audio_chunks = []

        # Guard rails
        if duration < 0.3:
            print(f"\n[Ignored recording: {duration:.2f}s is shorter than 0.3s]")
            return

        # Cap at 30 seconds
        max_bytes = int(self.sample_rate * 2 * 30.0)  # 2 bytes per sample, mono
        if len(raw_pcm) > max_bytes:
            raw_pcm = raw_pcm[:max_bytes]
            print("\n[Recording capped at 30 seconds]")

        print(f"\n[Processing {duration:.2f}s of audio...]")
        self._send_audio(raw_pcm)

    def _send_audio(self, raw_pcm: bytes):
        wav_bytes = build_wav_in_memory(raw_pcm, self.sample_rate)
        files = {"audio": ("audio.wav", wav_bytes, "audio/wav")}
        data: dict[str, Any] = {
            "device_id": "laptop-test",
            "context_text": self.box,
        }
        if self.languages:
            data["languages"] = ",".join(self.languages)

        endpoint = f"{self.url}/v1/process"
        start_req = time.perf_counter()
        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(endpoint, files=files, data=data)
        except httpx.ConnectError:
            print(f"[Error: Server is not running at {self.url}]")
            return
        except Exception as e:
            print(f"[Error connecting to server: {type(e).__name__}]")
            return

        round_trip_ms = (time.perf_counter() - start_req) * 1000.0

        if res.status_code != 200:
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text
            print(f"[Server Error {res.status_code}: {detail}]")
            return

        resp_data = res.json()
        action = resp_data.get("action")
        used_fallback = resp_data.get("used_fallback", False)
        note = resp_data.get("note")
        timings = resp_data.get("timings_ms") or {}

        # Save previous state to undo stack before applying
        self.undo_stack.append(self.box)
        self.box = apply_action(self.box, action)

        action_type = action.get("action") if action else "null"
        print("--------------------------------------------------")
        print(f"Action:        {action_type}")
        print(f"Used Fallback: {used_fallback}")
        print(f"Note:          {note or 'none'}")
        if timings:
            print(
                f"Timings:       read={timings.get('read_ms', 0):.1f}ms | "
                f"guardrail={timings.get('guardrail_ms', 0):.1f}ms | "
                f"stt={timings.get('stt_ms', 0):.1f}ms | "
                f"spark={timings.get('spark_ms', 0):.1f}ms | "
                f"server_total={timings.get('total_ms', 0):.1f}ms"
            )
        print(f"Round-trip:    {round_trip_ms:.1f}ms")
        print(f"Box Text:      \"{self.box}\"")
        print("--------------------------------------------------")

    def run_cli_loop(self):
        print("\nCommands: /undo, /clear, /show, /box <text>, /quit")
        while self.running:
            try:
                line = input()
            except (EOFError, KeyboardInterrupt):
                break
            line = line.strip()
            if not line:
                continue

            if line == "/quit":
                self.running = False
                break
            elif line == "/show":
                print(f"Box Text: \"{self.box}\"")
            elif line == "/undo":
                if self.undo_stack:
                    self.box = self.undo_stack.pop()
                    print(f"Restored Box: \"{self.box}\"")
                else:
                    print("[Undo stack is empty]")
            elif line == "/clear":
                self.box = ""
                self.undo_stack.clear()
                print("[Box and undo stack cleared]")
            elif line.startswith("/box"):
                new_text = line[4:].strip()
                self.undo_stack.append(self.box)
                self.box = new_text
                print(f"Box Text set to: \"{self.box}\"")
            else:
                print(
                    f"[Unknown command: {line}. Available: /undo, /clear, "
                    "/show, /box <text>, /quit]"
                )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Laptop voice test tool for Vboard /v1/process pipeline."
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://127.0.0.1:8000",
        help="Backend base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=24000,
        help="Audio sample rate: 24000 (default) or 16000",
    )
    parser.add_argument(
        "--lang",
        action="append",
        dest="languages",
        default=[],
        help="Language hint (repeatable, e.g. --lang Kannada --lang English)",
    )
    parser.add_argument(
        "--key",
        type=str,
        default="ctrl_r",
        help=(
            "Key to hold for recording (default: ctrl_r = Right Ctrl). "
            "Use a modifier key or combo: ctrl_r, shift_r, ctrl+shift, "
            "scroll_lock, pause. Do NOT use letter keys or function keys."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)

    if args.rate not in ALLOWED_RATES:
        sys.exit(
            f"Error: Invalid sample rate {args.rate}. Must be 24000 or 16000."
        )

    try:
        key_tuple = parse_key(args.key)
    except ValueError as e:
        sys.exit(f"Error: {e}")

    key_display = "+".join(k.upper() for k in key_tuple)

    # Lazy import devtools dependencies
    try:
        import pynput
        import sounddevice as sd
    except ImportError as e:
        sys.exit(
            f"Missing dependency: {e.name}. Install devtools with: "
            'pip install -e ".[devtools]"'
        )

    try:
        required_slots = resolve_pynput_keys(key_tuple, pynput.keyboard)
    except ValueError as e:
        sys.exit(f"Error: {e}")

    print("==================================================")
    print("VBOARD LAPTOP VOICE TEST")
    print(f"Backend URL:    {args.url}")
    print(f"Sample Rate:    {args.rate} Hz")
    print(f"Hotkey:         Hold and release {key_display}")
    print(f"Languages:      {args.languages or 'None'}")
    print("==================================================")

    app = VoiceTestApp(
        url=args.url,
        sample_rate=args.rate,
        key_display=key_display,
        languages=args.languages,
    )

    # Initialize audio input stream
    try:
        stream = sd.RawInputStream(
            samplerate=args.rate,
            channels=1,
            dtype="int16",
            callback=app._audio_callback,
        )
    except Exception as e:
        sys.exit(f"Failed to open default microphone: {e}")

    held_keys: set[Any] = set()

    def combo_active() -> bool:
        return all(any(k in held_keys for k in slot) for slot in required_slots)

    def on_press(key):
        held_keys.add(key)
        if combo_active():
            app.start_recording()

    def on_release(key):
        held_keys.discard(key)
        if app.is_recording and not combo_active():
            app.stop_and_send()

    listener = pynput.keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()

    with stream:
        app.run_cli_loop()


if __name__ == "__main__":
    main()
