"""Eval audio dataset downloader — Kannada, Hindi, English (5 samples each)."""
import csv
import io
import os
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from datasets import Audio, load_dataset
from dotenv import load_dotenv

# ── Constants ───────────────────────────────────────────────────────────────
SAMPLES_PER_LANGUAGE = 5
MIN_WORDS = 5
TARGET_SAMPLE_RATE = 16000
MIN_SECONDS = 25.0
MAX_SECONDS = 300.0


EVAL_DIR = Path(__file__).resolve().parent
AUDIO_DIR = EVAL_DIR / "audio"
CSV_PATH = EVAL_DIR / "metadata.csv"

# ── HF Token (settings object → .env fallback) ──────────────────────────────
load_dotenv()
try:
    if str(EVAL_DIR.parent) not in sys.path:
        sys.path.insert(0, str(EVAL_DIR.parent))
    from app.core.config import settings
    HF_TOKEN: str | None = getattr(settings, "HF_TOKEN", None) or os.getenv("HF_TOKEN")
except Exception:
    HF_TOKEN = os.getenv("HF_TOKEN")

# ── Dataset configs ──────────────────────────────────────────────────────────
DATASETS = [
    dict(language="Kannada", path="ai4bharat/IndicVoices", name="kannada",
         split="train", audio_col="audio_filepath", text_col="text"),
    dict(language="Hindi",   path="ai4bharat/IndicVoices", name="hindi",
         split="train", audio_col="audio_filepath", text_col="text"),
    dict(language="English", path="openslr/librispeech_asr", name="clean",
         split="test",  audio_col="audio",          text_col="text"),
]


# ── Helpers ──────────────────────────────────────────────────────────────────
def _load_audio(audio_dict: dict) -> tuple[np.ndarray, int]:
    raw = audio_dict.get("bytes")
    return sf.read(io.BytesIO(raw) if raw else audio_dict["path"])


def _to_16k(data: np.ndarray, sr: int) -> np.ndarray:
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != TARGET_SAMPLE_RATE:
        data = librosa.resample(data.astype(np.float32), orig_sr=sr, target_sr=TARGET_SAMPLE_RATE)
    return np.asarray(data, dtype=np.float32)


def save_samples(language: str, dataset, audio_col: str, text_col: str) -> list[dict]:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    rows, saved = [], 0

    for sample in dataset:
        transcript = (sample.get(text_col) or "").strip()
        if len(transcript.split()) <= MIN_WORDS:
            continue

        audio_dict = sample.get(audio_col)
        if not audio_dict:
            continue

        try:
            data, sr = _load_audio(audio_dict)
        except Exception:
            continue

        if not (MIN_SECONDS <= len(data) / sr <= MAX_SECONDS):
            continue

        saved += 1
        out_path = AUDIO_DIR / f"{language.lower()}_{saved}.wav"
        if out_path.exists():
            out_path.unlink()
        sf.write(str(out_path), _to_16k(data, sr), TARGET_SAMPLE_RATE)

        rows.append({"file_path": f"audio/{out_path.name}", "language": language,
                     "transcript": transcript})
        if saved >= SAMPLES_PER_LANGUAGE:
            break

    return rows


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []

    for cfg in DATASETS:
        print(f"[{cfg['language']}] Loading {cfg['path']} ({cfg['name']})...")
        ds = load_dataset(path=cfg["path"], name=cfg["name"], split=cfg["split"],
                          streaming=True, **({"token": HF_TOKEN} if HF_TOKEN else {}))
        ds = ds.cast_column(cfg["audio_col"], Audio(decode=False))
        rows = save_samples(cfg["language"], ds, cfg["audio_col"], cfg["text_col"])
        print(f"[{cfg['language']}] Saved {len(rows)} samples.")
        all_rows.extend(rows)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path", "language", "transcript"])
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nDone! {len(all_rows)} samples -> {CSV_PATH}")


if __name__ == "__main__":
    main()
