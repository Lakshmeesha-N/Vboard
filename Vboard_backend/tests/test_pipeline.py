from unittest.mock import AsyncMock, patch

import pytest

from app.services import pipeline
from app.services.action_service import Action, ActionResult
from app.services.stt_service import TranscriptionResult
from tests.test_audio import create_in_memory_wav


@pytest.mark.asyncio
async def test_pipeline_run_success_and_timings():
    wav_bytes = create_in_memory_wav(sample_rate=16000, duration_s=1.0)
    mock_stt = TranscriptionResult(
        transcript="Test pipeline",
        elapsed_ms=85.0,
        audio_duration_ms=1000,
    )
    mock_action = ActionResult(
        action=Action(action="insert", text="Test pipeline", find="", which="last"),
        used_fallback=False,
        fallback_reason=None,
        elapsed_ms=45.0,
        prompt_tokens=30,
        completion_tokens=15,
        cached_tokens=0,
        reasoning_tokens=5,
    )

    with (
        patch(
            "app.services.stt_service.transcribe",
            new=AsyncMock(return_value=mock_stt),
        ) as mock_transcribe,
        patch(
            "app.services.action_service.process",
            new=AsyncMock(return_value=mock_action),
        ) as mock_process,
    ):
        res = await pipeline.run(
            wav_bytes,
            languages=["Kannada"],
            context_text="box context",
        )

    mock_transcribe.assert_awaited_once_with(wav_bytes, languages=["Kannada"])
    mock_process.assert_awaited_once_with("Test pipeline", "box context")

    assert res.transcript == "Test pipeline"
    assert res.audio_duration_ms == 1000
    assert res.action == Action(
        action="insert", text="Test pipeline", find="", which="last"
    )
    assert res.used_fallback is False
    assert res.fallback_reason is None
    assert res.prompt_tokens == 30
    assert res.completion_tokens == 15
    assert "guardrail_ms" in res.timings_ms
    assert "stt_ms" in res.timings_ms
    assert "spark_ms" in res.timings_ms
    assert "total_ms" in res.timings_ms
    assert res.timings_ms["guardrail_ms"] >= 0
    assert res.timings_ms["stt_ms"] >= 0
    assert res.timings_ms["spark_ms"] >= 0
    assert (
        res.timings_ms["total_ms"]
        >= round(
            res.timings_ms["guardrail_ms"]
            + res.timings_ms["stt_ms"]
            + res.timings_ms["spark_ms"],
            2,
        )
        - 0.01
    )
