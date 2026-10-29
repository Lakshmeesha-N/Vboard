import io
import math
import struct
import wave
from unittest.mock import patch

import pytest

from app.core.audio import (
    ALLOWED_CHANNELS,
    ALLOWED_SAMPLE_WIDTH,
    AudioValidationResult,
    validate_wav_bytes,
)
from app.core.config import settings
from app.core.exceptions import InvalidAudioError


def create_in_memory_wav(
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
    duration_s: float = 1.0,
    frequency: float = 440.0,
    amplitude: float = 16000.0,
) -> bytes:
    """Generate in-memory WAV bytes with pure sine wave PCM audio."""
    buf = io.BytesIO()
    num_frames = int(sample_rate * duration_s)

    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)

        frames = bytearray()
        for i in range(num_frames):
            val = (
                int(amplitude * math.sin(2 * math.pi * frequency * (i / sample_rate)))
                if amplitude > 0
                else 0
            )
            if sample_width == 2:
                frame = struct.pack("<h", max(-32768, min(32767, val)))
            elif sample_width == 1:
                frame = struct.pack("<B", max(0, min(255, val + 128)))
            elif sample_width == 3:
                # 24-bit PCM
                clipped = max(-8388608, min(8388607, val * 256))
                frame = struct.pack("<i", clipped)[:3]
            else:
                frame = b"\x00" * sample_width

            frames.extend(frame * channels)

        wf.writeframes(bytes(frames))

    return buf.getvalue()


def test_valid_16k_wav_passes():
    wav_bytes = create_in_memory_wav(sample_rate=16000, duration_s=1.0)
    res = validate_wav_bytes(wav_bytes)

    assert isinstance(res, AudioValidationResult)
    assert res.channels == ALLOWED_CHANNELS
    assert res.sample_rate == 16000
    assert res.sample_width == ALLOWED_SAMPLE_WIDTH
    assert 0.99 <= res.duration_s <= 1.01
    assert res.rms > settings.SILENCE_RMS_THRESHOLD


def test_valid_24k_wav_passes():
    wav_bytes = create_in_memory_wav(sample_rate=24000, duration_s=1.5)
    res = validate_wav_bytes(wav_bytes)

    assert isinstance(res, AudioValidationResult)
    assert res.channels == ALLOWED_CHANNELS
    assert res.sample_rate == 24000
    assert res.sample_width == ALLOWED_SAMPLE_WIDTH
    assert 1.49 <= res.duration_s <= 1.51
    assert res.rms > settings.SILENCE_RMS_THRESHOLD


def test_empty_audio_buffer_raises():
    with pytest.raises(InvalidAudioError) as exc_info:
        validate_wav_bytes(b"")
    assert exc_info.value.status_code == 400
    assert "empty" in str(exc_info.value).lower()


def test_oversized_audio_buffer_raises_413():
    fake_oversized = b"RIFF" + b"\x00" * (settings.MAX_AUDIO_BYTES + 10)
    with pytest.raises(InvalidAudioError) as exc_info:
        validate_wav_bytes(fake_oversized)
    assert exc_info.value.status_code == 413
    assert "exceeds maximum size" in str(exc_info.value).lower()


def test_corrupted_non_wav_raises():
    with pytest.raises(InvalidAudioError) as exc_info:
        validate_wav_bytes(b"NOT_A_WAV_FILE_AT_ALL_GARBAGE_BYTES")
    assert exc_info.value.status_code == 400
    assert "invalid wav" in str(exc_info.value).lower()


def test_stereo_rejected():
    stereo_wav = create_in_memory_wav(sample_rate=16000, channels=2, duration_s=1.0)
    with pytest.raises(InvalidAudioError) as exc_info:
        validate_wav_bytes(stereo_wav)
    assert exc_info.value.status_code == 400
    assert "mono" in str(exc_info.value).lower()


@pytest.mark.parametrize("rate", [8000, 11025, 44100, 48000])
def test_unsupported_sample_rates_rejected(rate):
    wav_bytes = create_in_memory_wav(sample_rate=rate, duration_s=1.0)
    with pytest.raises(InvalidAudioError) as exc_info:
        validate_wav_bytes(wav_bytes)
    assert exc_info.value.status_code == 400
    assert "sample rate" in str(exc_info.value).lower()


@pytest.mark.parametrize("width", [1, 3])
def test_unsupported_sample_widths_rejected(width):
    wav_bytes = create_in_memory_wav(
        sample_rate=16000, sample_width=width, duration_s=1.0
    )
    with pytest.raises(InvalidAudioError) as exc_info:
        validate_wav_bytes(wav_bytes)
    assert exc_info.value.status_code == 400
    assert "16-bit pcm" in str(exc_info.value).lower()


def test_duration_under_minimum_rejected():
    short_wav = create_in_memory_wav(sample_rate=16000, duration_s=0.15)
    with pytest.raises(InvalidAudioError) as exc_info:
        validate_wav_bytes(short_wav)
    assert exc_info.value.status_code == 400
    assert "less than minimum" in str(exc_info.value).lower()


def test_duration_over_maximum_rejected():
    # Build a minimal WAV header indicating 65 seconds
    wav_bytes = create_in_memory_wav(sample_rate=16000, duration_s=61.0)
    with pytest.raises(InvalidAudioError) as exc_info:
        validate_wav_bytes(wav_bytes)
    assert exc_info.value.status_code == 400
    assert "exceeds maximum" in str(exc_info.value).lower()


def test_duration_calculated_from_actual_frames_not_spoofed_header():
    # Construct a valid WAV of 0.1s (too short)
    short_wav = create_in_memory_wav(sample_rate=16000, duration_s=0.15)

    # Even if header claims more or we truncate the actual data chunk:
    truncated_wav = short_wav[: len(short_wav) - 200]
    # Truncated frames will fail either wave parsing or actual frames check
    with pytest.raises(InvalidAudioError) as exc_info:
        validate_wav_bytes(truncated_wav)
    assert exc_info.value.status_code == 400


def test_silence_detection_subsampled_array():
    silent_wav = create_in_memory_wav(sample_rate=16000, duration_s=1.0, amplitude=0.0)
    with pytest.raises(InvalidAudioError) as exc_info:
        validate_wav_bytes(silent_wav)
    assert exc_info.value.status_code == 400
    assert "silent" in str(exc_info.value).lower()


def test_zero_disk_writes():
    wav_bytes = create_in_memory_wav(sample_rate=16000, duration_s=1.0)
    with patch("builtins.open") as mock_open:
        res = validate_wav_bytes(wav_bytes)
        assert res.sample_rate == 16000
        mock_open.assert_not_called()
