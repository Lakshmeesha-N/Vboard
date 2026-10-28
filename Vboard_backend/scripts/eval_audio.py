import argparse
import asyncio
import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

import jiwer

from app.services.meta_client import close_meta_client, init_meta_client
from app.services.stt_service import transcribe

# Project root: Vboard_backend
BASE_DIR = Path(__file__).resolve().parent.parent
EVAL_DIR = BASE_DIR / "eval"
METADATA_PATH = EVAL_DIR / "metadata.csv"
RESULTS_DIR = EVAL_DIR / "results"


def normalize_text(text: str) -> str:
    """
    Normalise text for speech recognition evaluation:
    1. Unicode NFC
    2. Lowercase
    3. Strip punctuation characters (Unicode category 'P') while keeping apostrophes (')
    4. Collapse whitespace
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text).lower()
    # Strip characters in punctuation categories, preserving apostrophe
    text = "".join(
        c for c in text if not (unicodedata.category(c).startswith("P") and c != "'")
    )
    return re.sub(r"\s+", " ", text).strip()


def check_formatting_difference(reference: str, hypothesis: str) -> bool:
    """
    Returns True if hypothesis has digits or Latin characters while reference has none.
    """
    hyp_has_digits_latin = bool(re.search(r"[0-9a-zA-Z]", hypothesis))
    ref_has_digits_latin = bool(re.search(r"[0-9a-zA-Z]", reference))
    return hyp_has_digits_latin and not ref_has_digits_latin


async def run_evaluation(
    lang_flag: Optional[str] = None,
    only_filter: Optional[str] = None,
    show_transcripts: bool = False,
) -> None:
    """Run sequential evaluation over eval/metadata.csv audio clips."""
    if not METADATA_PATH.exists():
        print(f"Error: Metadata file not found at {METADATA_PATH}")
        return

    languages_hint = (
        [item.strip() for item in lang_flag.split(",") if item.strip()]
        if lang_flag
        else None
    )

    with open(METADATA_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    if only_filter:
        rows = [r for r in all_rows if only_filter in r.get("file_path", "")]
    else:
        rows = all_rows

    if not rows:
        print("No matching audio clips found to evaluate.")
        return

    print(f"\nStarting evaluation of {len(rows)} clips...")
    print(f"Language hint: {languages_hint or 'None'}")
    if only_filter:
        print(f"Filter: '{only_filter}'")
    print("-" * 80)

    # Initialize shared Meta HTTP client
    await init_meta_client()

    results: list[dict] = []
    try:
        for idx, row in enumerate(rows, start=1):
            rel_path = row["file_path"].strip()
            language = row.get("language", "Unknown").strip()
            raw_ref = row.get("transcript", "").strip()

            wav_path = EVAL_DIR / rel_path
            if not wav_path.exists():
                print(f"[{idx}/{len(rows)}] Skipping missing audio: {rel_path}")
                continue

            with open(wav_path, "rb") as audio_file:
                wav_bytes = audio_file.read()

            try:
                transcription = await transcribe(wav_bytes, languages=languages_hint)
            except Exception as exc:
                print(f"[{idx}/{len(rows)}] Error transcribing {rel_path}: {exc}")
                continue

            raw_hyp = transcription.transcript
            norm_ref = normalize_text(raw_ref)
            norm_hyp = normalize_text(raw_hyp)

            # Compute WER and CER via jiwer
            clip_wer = jiwer.wer(norm_ref, norm_hyp) if norm_ref else 0.0
            clip_cer = jiwer.cer(norm_ref, norm_hyp) if norm_ref else 0.0

            formatting_flag = ""
            if check_formatting_difference(norm_ref, norm_hyp):
                formatting_flag = "formatting difference, check by eye"

            clip_result = {
                "file_path": rel_path,
                "language": language,
                "reference": raw_ref,
                "transcript": raw_hyp,
                "norm_reference": norm_ref,
                "norm_transcript": norm_hyp,
                "wer": clip_wer,
                "cer": clip_cer,
                "latency_ms": transcription.elapsed_ms,
                "audio_duration_ms": transcription.audio_duration_ms,
                "flag": formatting_flag,
            }
            results.append(clip_result)

            status_note = f" | [{formatting_flag}]" if formatting_flag else ""
            print(
                f"[{idx}/{len(rows)}] {rel_path} ({language}) - "
                f"WER: {clip_wer * 100:.1f}%, CER: {clip_cer * 100:.1f}%, "
                f"Latency: {transcription.elapsed_ms:.0f}ms{status_note}"
            )

            if show_transcripts:
                print(f"  Ref: {raw_ref}")
                print(f"  Hyp: {raw_hyp}")

    finally:
        await close_meta_client()

    if not results:
        print("No evaluation results were recorded.")
        return

    # Print summary table
    print("\n" + "=" * 90)
    print(
        f"{'Clip':<24} {'Lang':<10} {'WER':<8} {'CER':<8} "
        f"{'Latency':<10} {'Audio':<10} {'Notes'}"
    )
    print("=" * 90)
    for res in results:
        clip_name = Path(res["file_path"]).name
        wer_str = f"{res['wer'] * 100:.1f}%"
        cer_str = f"{res['cer'] * 100:.1f}%"
        lat_str = f"{res['latency_ms']:.0f}ms"
        dur_str = f"{res['audio_duration_ms']}ms"
        print(
            f"{clip_name:<24} {res['language']:<10} {wer_str:<8} {cer_str:<8} "
            f"{lat_str:<10} {dur_str:<10} {res['flag']}"
        )

    # Calculate summaries by language and overall
    print("\n" + "-" * 60)
    print("EVALUATION SUMMARY")
    print("-" * 60)

    languages_present = sorted(list({r["language"] for r in results}))
    for lang in languages_present:
        lang_res = [r for r in results if r["language"] == lang]
        avg_wer = sum(r["wer"] for r in lang_res) / len(lang_res)
        avg_cer = sum(r["cer"] for r in lang_res) / len(lang_res)
        avg_lat = sum(r["latency_ms"] for r in lang_res) / len(lang_res)
        max_lat = max(r["latency_ms"] for r in lang_res)
        print(
            f"Language: {lang:<10} (clips: {len(lang_res)})\n"
            f"  Avg WER: {avg_wer * 100:.2f}%\n"
            f"  Avg CER: {avg_cer * 100:.2f}%\n"
            f"  Avg Latency: {avg_lat:.1f}ms\n"
            f"  Max Latency: {max_lat:.1f}ms"
        )

    overall_avg_wer = sum(r["wer"] for r in results) / len(results)
    overall_avg_cer = sum(r["cer"] for r in results) / len(results)
    overall_avg_lat = sum(r["latency_ms"] for r in results) / len(results)
    overall_max_lat = max(r["latency_ms"] for r in results)
    print("-" * 60)
    print(
        f"OVERALL (clips: {len(results)})\n"
        f"  Avg WER: {overall_avg_wer * 100:.2f}%\n"
        f"  Avg CER: {overall_avg_cer * 100:.2f}%\n"
        f"  Avg Latency: {overall_avg_lat:.1f}ms\n"
        f"  Max Latency: {overall_max_lat:.1f}ms"
    )
    print("=" * 60)

    # Save run to CSV in eval/results/
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = RESULTS_DIR / f"run_{timestamp}.csv"

    fieldnames = [
        "run_timestamp",
        "lang_flag",
        "file_path",
        "language",
        "wer",
        "cer",
        "latency_ms",
        "audio_duration_ms",
        "flag",
        "reference",
        "transcript",
    ]

    with open(out_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "run_timestamp": timestamp,
                    "lang_flag": lang_flag or "",
                    "file_path": r["file_path"],
                    "language": r["language"],
                    "wer": f"{r['wer']:.4f}",
                    "cer": f"{r['cer']:.4f}",
                    "latency_ms": f"{r['latency_ms']:.1f}",
                    "audio_duration_ms": r["audio_duration_ms"],
                    "flag": r["flag"],
                    "reference": r["reference"],
                    "transcript": r["transcript"],
                }
            )

    print(f"\nRun results saved to: {out_file}\n")


def main() -> None:
    """CLI entrypoint for audio evaluation."""
    parser = argparse.ArgumentParser(
        description="Measure ASR WER/CER and latency using Meta Muse Voice Transcribe."
    )
    parser.add_argument(
        "--lang",
        type=str,
        default=None,
        help="Comma-separated language bias hints (e.g. Kannada,English).",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Run only clips whose file_path contains this string.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Print reference and transcript output under each clip.",
    )

    args = parser.parse_args()
    asyncio.run(
        run_evaluation(
            lang_flag=args.lang,
            only_filter=args.only,
            show_transcripts=args.show,
        )
    )


if __name__ == "__main__":
    main()
