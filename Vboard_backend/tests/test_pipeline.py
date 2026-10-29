from unittest.mock import AsyncMock, patch

import pytest

from app.services import pipeline
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

    with patch(
        "app.services.stt_service.transcribe",
        new=AsyncMock(return_value=mock_stt),
    ) as mock_transcribe:
        res = await pipeline.run(wav_bytes, languages=["Kannada"])

    mock_transcribe.assert_awaited_once_with(wav_bytes, languages=["Kannada"])
    assert res.transcript == "Test pipeline"
    assert res.audio_duration_ms == 1000
    assert "guardrail_ms" in res.timings_ms
    assert "stt_ms" in res.timings_ms
    assert "total_ms" in res.timings_ms
    assert res.timings_ms["guardrail_ms"] >= 0
    assert res.timings_ms["stt_ms"] >= 0
    assert res.timings_ms["total_ms"] >= res.timings_ms["guardrail_ms"]

