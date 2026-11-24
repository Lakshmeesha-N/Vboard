import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.core.exceptions import MetaApiError, RateLimitedError
from app.services import llm_service

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@dataclass
class AgentResult:
    text: str
    elapsed_ms: float


def _load_prompt(filename: str) -> str:
    """Load prompt content from app/prompts directory."""
    path = _PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


async def cleanup_branch(
    content: str, languages: Optional[str] = None
) -> AgentResult:
    """Execute grammar, punctuation, and translation cleanup using LLM."""
    system_prompt = _load_prompt("text_system.md")

    async def _call_complete() -> llm_service.LLMResult:
        return await llm_service.complete(
            system_prompt, content, reasoning_effort="minimal"
        )

    try:
        result = await _call_complete()
    except RateLimitedError:
        raise
    except MetaApiError:
        await asyncio.sleep(1)
        result = await _call_complete()

    if not result.text.strip():
        await asyncio.sleep(1)
        try:
            result = await _call_complete()
        except RateLimitedError:
            raise
        except MetaApiError as exc:
            raise MetaApiError("Empty response from LLM") from exc

        if not result.text.strip():
            raise MetaApiError("Empty response from LLM")

    return AgentResult(
        text=result.text,
        elapsed_ms=result.elapsed_ms,
    )
