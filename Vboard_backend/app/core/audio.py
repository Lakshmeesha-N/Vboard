import array
import io
import math
import wave
from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import InvalidAudioError

ALLOWED_SAMPLE_RATES = (16000, 24000)
ALLOWED_CHANNELS = 1
ALLOWED_SAMPLE_WIDTH = 2  # 16-bit PCM

META_SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {
        "Arabic",
        "Bengali",
        "Dutch",
        "English",
        "French",
        "German",
        "Hebrew",
        "Hindi",
        "Indonesian",
        "Italian",
        "Japanese",
        "Kannada",
        "Korean",
        "Malay",
        "Mandarin Chinese",
        "Marathi",
        "Polish",
        "Portuguese",
        "Spanish",
        "Tagalog",
        "Tamil",
        "Telugu",
        "Thai",
        "Turkish",
        "Vietnamese",
    }
)


@dataclass(frozen=True)
class AudioValidationResult:
    """Validated audio properties."""

    channels: int
    sample_rate: int
    sample_width: int
    duration_s: float
    rms: float


def validate_wav_bytes(wav_bytes: bytes) -> AudioValidationResult:
    """
    Validate raw WAV audio bytes strictly in-memory with zero disk writes.

    Performs:
    1. Size verification (rejects empty or > MAX_AUDIO_BYTES).
    2. Header & container validation (mono, 16-bit PCM, 16kHz or 24kHz).
    3. Frame extraction & actual duration calculation (0.3s to 60.0s).
    4. Silence check via subsampled 16-bit PCM RMS amplitude.

    Args:
        wav_bytes: Raw audio byte string.

    Returns:
        AudioValidationResult dataclass with audio metrics.

    Raises:
        InvalidAudioError: On any format, size, duration, or silence violation.
    """
    if not wav_bytes:
        raise InvalidAudioError("Audio payload is empty", status_code=400)

    if len(wav_bytes) > settings.MAX_AUDIO_BYTES:
        max_mb = settings.MAX_AUDIO_BYTES // (1024 * 1024)
        raise InvalidAudioError(
            f"Audio payload exceeds maximum size limit of {max_mb} MB",
            status_code=413,
        )

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            sample_width = wf.getsampwidth()

            if channels != ALLOWED_CHANNELS:
                raise InvalidAudioError(
                    f"Audio must be mono (1 channel), got {channels} channels",
                    status_code=400,
                )

            if sample_width != ALLOWED_SAMPLE_WIDTH:
                raise InvalidAudioError(
                    f"Audio must be 16-bit PCM ({ALLOWED_SAMPLE_WIDTH} bytes/sample), "
                    f"got {sample_width} bytes/sample",
                    status_code=400,
                )

            if sample_rate not in ALLOWED_SAMPLE_RATES:
                raise InvalidAudioError(
                    f"Sample rate must be 16000Hz or 24000Hz, got {sample_rate}Hz",
                    status_code=400,
                )

            # Read actual raw frame data from container
            raw_frames = wf.readframes(wf.getnframes())
    except wave.Error:
        raise InvalidAudioError("Invalid WAV audio format", status_code=400) from None

    frame_bytes_per_sample = channels * sample_width
    actual_frames = len(raw_frames) // frame_bytes_per_sample

    if actual_frames == 0:
        raise InvalidAudioError(
            "Audio payload contains no audio frames",
            status_code=400,
        )

    # Compute duration from actual frames read to prevent spoofed headers
    duration_s = actual_frames / sample_rate

    if duration_s < settings.MIN_AUDIO_DURATION_S:
        raise InvalidAudioError(
            f"Audio duration {duration_s:.2f}s is less than "
            f"minimum {settings.MIN_AUDIO_DURATION_S}s",
            status_code=400,
        )

    if duration_s > settings.MAX_AUDIO_DURATION_S:
        raise InvalidAudioError(
            f"Audio duration {duration_s:.2f}s exceeds "
            f"maximum {settings.MAX_AUDIO_DURATION_S}s",
            status_code=400,
        )

    # Silence check using pure array (no audioop), checking every 10th sample for speed
    samples = array.array("h")
    # Slice only the valid frame bytes to ensure exact alignment
    valid_bytes_len = actual_frames * frame_bytes_per_sample
    samples.frombytes(raw_frames[:valid_bytes_len])

    sub_samples = samples[::10]
    if not sub_samples:
        raise InvalidAudioError(
            "Audio payload contains no audio samples", status_code=400
        )

    sum_sq = sum(s * s for s in sub_samples)
    rms = math.sqrt(sum_sq / len(sub_samples))

    if rms <= settings.SILENCE_RMS_THRESHOLD:
        raise InvalidAudioError("Audio is completely silent", status_code=400)

    return AudioValidationResult(
        channels=channels,
        sample_rate=sample_rate,
        sample_width=sample_width,
        duration_s=round(duration_s, 3),
        rms=round(rms, 2),
    )
