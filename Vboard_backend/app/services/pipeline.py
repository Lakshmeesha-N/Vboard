import time
from dataclasses import dataclass
from typing import Optional

from app.core.audio import validate_wav_bytes
from app.services import stt_service


@dataclass(frozen=True)
class PipelineResult:
    """Consolidated pipeline processing output and stage timings."""

    transcript: str
    audio_duration_ms: int
    timings_ms: dict[str, float]


async def run(
    wav_bytes: bytes,
    languages: Optional[list[str]] = None,
) -> PipelineResult:
    """
    Execute speech processing pipeline: guardrail -> STT (later Spark).

    Measures execution time for each stage with time.perf_counter().
    Maintains zero audio and zero transcript logging.
    """
    total_start = time.perf_counter()

    # Stage 1: In-memory Audio Guardrail
    guardrail_start = time.perf_counter()
    validate_wav_bytes(wav_bytes)
    guardrail_ms = (time.perf_counter() - guardrail_start) * 1000.0

    # Stage 2: Meta Muse STT Transcription
    stt_start = time.perf_counter()
    stt_res = await stt_service.transcribe(wav_bytes, languages=languages)
    stt_ms = (time.perf_counter() - stt_start) * 1000.0

    total_ms = (time.perf_counter() - total_start) * 1000.0

    timings = {
        "guardrail_ms": round(guardrail_ms, 2),
        "stt_ms": round(stt_ms, 2),
        "total_ms": round(total_ms, 2),
    }

    return PipelineResult(
        transcript=stt_res.transcript,
        audio_duration_ms=stt_res.audio_duration_ms,
        timings_ms=timings,
    )

