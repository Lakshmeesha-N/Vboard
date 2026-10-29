from pathlib import Path

_PROMPT_PATH = Path(__file__).resolve().parent / "spark_system.md"
SPARK_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

__all__ = ["SPARK_SYSTEM_PROMPT"]
