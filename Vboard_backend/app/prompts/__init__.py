from pathlib import Path

_PROMPT_PATH = Path(__file__).resolve().parent / "voice_system.md"
VOICE_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

__all__ = ["VOICE_SYSTEM_PROMPT"]
