import argparse
import asyncio
import csv
import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import jiwer

from app.core.config import settings
from app.services.action_service import process
from app.services.llm_client import close_llm_client, init_llm_client

# Project root: Vboard_backend
BASE_DIR = Path(__file__).resolve().parent.parent
EVAL_DIR = BASE_DIR / "eval"
DEFAULT_CSV_PATH = EVAL_DIR / "texttest.csv"
RESULTS_DIR = EVAL_DIR / "results"

# Spark 1.3 Standard pricing (USD per 1,000,000 tokens)
PRICE_INPUT_PER_1M = 1.25
PRICE_CACHED_INPUT_PER_1M = 0.15
PRICE_OUTPUT_PER_1M = 4.25

REQUIRED_COLUMNS = [
    "id",
    "mix",
    "box_text",
    "spoken_text",
    "expected_action",
    "expected_find",
    "expected_which",
    "expected_text",
    "notes",
]

ACTION_TYPES = ["insert", "replace", "rewrite", "none"]


def calculate_spark_cost(
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Calculate estimated USD cost for Spark 1.3 Standard."""
    uncached_input = max(0, prompt_tokens - cached_tokens)
    input_cost = (uncached_input * PRICE_INPUT_PER_1M) / 1_000_000.0
    cached_cost = (cached_tokens * PRICE_CACHED_INPUT_PER_1M) / 1_000_000.0
    output_cost = (completion_tokens * PRICE_OUTPUT_PER_1M) / 1_000_000.0
    return input_cost + cached_cost + output_cost


def normalize_text(text: str) -> str:
    """
    Normalise text for CER scoring:
    1. Unicode NFC
    2. Lowercase
    3. Strip punctuation category P except apostrophe (')
    4. Collapse whitespace
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text).lower()
    text = "".join(
        c for c in text if not (unicodedata.category(c).startswith("P") and c != "'")
    )
    return re.sub(r"\s+", " ", text).strip()


def compute_percentile(data: list[float], percentile: float) -> float:
    """Compute given percentile (0-100) using linear interpolation."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    rank = (percentile / 100.0) * (n - 1)
    low_idx = int(math.floor(rank))
    high_idx = int(math.ceil(rank))
    if low_idx == high_idx:
        return sorted_data[low_idx]
    weight = rank - low_idx
    return sorted_data[low_idx] * (1.0 - weight) + sorted_data[high_idx] * weight


def load_eval_rows(csv_path: Path) -> list[dict[str, str]]:
    """Load and validate evaluation rows from CSV."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Evaluation CSV not found: {csv_path}")

    rows: list[dict[str, str]] = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Empty or invalid CSV file: {csv_path}")

        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise ValueError(
                f"CSV missing required columns: {missing}. Found: {reader.fieldnames}"
            )

        for line_num, r in enumerate(reader, start=2):
            row_id = r.get("id", "").strip()
            exp_action = r.get("expected_action", "").strip().lower()
            if not row_id:
                raise ValueError(f"Line {line_num}: missing 'id'")
            if exp_action not in ACTION_TYPES:
                raise ValueError(
                    f"Line {line_num} (id={row_id}): "
                    f"invalid expected_action '{exp_action}'"
                )
            if exp_action == "replace":
                exp_which = r.get("expected_which", "").strip().lower()
                if not exp_which:
                    raise ValueError(
                        f"Line {line_num} (id={row_id}): "
                        "replace action requires expected_which"
                    )
            rows.append(r)

    return rows


def score_row(row: dict[str, str], result: Any) -> dict[str, Any]:
    """Score a single evaluation result against expected values."""
    expected_action = row["expected_action"].strip().lower()
    expected_find = row.get("expected_find", "").strip()
    expected_which = row.get("expected_which", "").strip().lower()
    expected_text = row.get("expected_text", "").strip()

    action_obj = result.action
    got_action = action_obj.action.lower() if action_obj else "none"
    got_find = action_obj.find.strip() if action_obj else ""
    got_which = action_obj.which.strip().lower() if action_obj else ""
    got_text = action_obj.text if action_obj else ""

    action_ok = got_action == expected_action
    find_ok: Optional[bool] = None
    which_ok: Optional[bool] = None

    if expected_action == "replace":
        find_ok = got_find == expected_find
        which_ok = got_which == expected_which
        is_pass = action_ok and bool(find_ok) and bool(which_ok)
    elif expected_action == "none":
        is_pass = action_ok and (result.fallback_reason == "find_not_found")
    else:
        is_pass = action_ok

    # CER scoring
    text_cer: Optional[float] = None
    review_flag = ""
    if expected_text:
        norm_exp = normalize_text(expected_text)
        norm_got = normalize_text(got_text)
        if norm_exp:
            text_cer = float(jiwer.cer(norm_exp, norm_got))
            if text_cer > 0.2:
                review_flag = "review text"

    cost_usd = calculate_spark_cost(
        result.prompt_tokens,
        result.completion_tokens,
        result.cached_tokens,
    )

    return {
        "id": row["id"].strip(),
        "mix": row.get("mix", "").strip(),
        "expected_action": expected_action,
        "got_action": got_action,
        "expected_find": expected_find,
        "got_find": got_find,
        "expected_which": expected_which,
        "got_which": got_which,
        "got_text": got_text,
        "action_ok": action_ok,
        "find_ok": find_ok,
        "which_ok": which_ok,
        "text_cer": text_cer,
        "review_flag": review_flag,
        "pass": is_pass,
        "used_fallback": result.used_fallback,
        "fallback_reason": result.fallback_reason or "",
        "elapsed_ms": result.elapsed_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "cached_tokens": result.cached_tokens,
        "reasoning_tokens": result.reasoning_tokens,
        "cost_usd": cost_usd,
        "notes": row.get("notes", "").strip(),
    }


def print_confusion_matrix(scores: list[dict[str, Any]]) -> None:
    """Print confusion matrix for expected vs got action types."""
    matrix: dict[str, dict[str, int]] = {
        exp: {got: 0 for got in ACTION_TYPES} for exp in ACTION_TYPES
    }
    for s in scores:
        exp = s["expected_action"]
        got = s["got_action"]
        if exp in matrix and got in matrix[exp]:
            matrix[exp][got] += 1

    print("\n--- Action Confusion Matrix (Expected \\ Got) ---")
    header = f"{'Expected':<10} | " + " | ".join(f"{a:>7}" for a in ACTION_TYPES)
    print(header)
    print("-" * len(header))
    for exp in ACTION_TYPES:
        row_str = f"{exp:<10} | " + " | ".join(
            f"{matrix[exp][got]:>7}" for got in ACTION_TYPES
        )
        print(row_str)


def print_summary_tables(scores: list[dict[str, Any]]) -> None:
    """Print overall metrics and breakdown by language mix."""
    total = len(scores)
    if total == 0:
        return

    passes = sum(1 for s in scores if s["pass"])
    action_correct = sum(1 for s in scores if s["action_ok"])
    fallbacks = sum(1 for s in scores if s["used_fallback"])

    latencies = [s["elapsed_ms"] for s in scores]
    avg_lat = sum(latencies) / total
    p50_lat = compute_percentile(latencies, 50.0)
    p95_lat = compute_percentile(latencies, 95.0)
    max_lat = max(latencies)

    tot_prompt = sum(s["prompt_tokens"] for s in scores)
    tot_completion = sum(s["completion_tokens"] for s in scores)
    tot_cached = sum(s["cached_tokens"] for s in scores)
    tot_reasoning = sum(s["reasoning_tokens"] for s in scores)
    tot_cost = sum(s["cost_usd"] for s in scores)

    print("\n" + "=" * 80)
    print("EVAL-LLM SUMMARY")
    print("=" * 80)
    print(f"Total Rows Evaluated: {total}")
    print(f"Pass Rate:            {passes}/{total} ({passes / total * 100:.1f}%)")
    print(
        f"Action Accuracy:      {action_correct}/{total} "
        f"({action_correct / total * 100:.1f}%)"
    )
    print(f"Fallbacks Used:       {fallbacks}")

    # Fallback reasons breakdown
    if fallbacks > 0:
        reasons: dict[str, int] = {}
        for s in scores:
            if s["used_fallback"]:
                r = s["fallback_reason"] or "unknown"
                reasons[r] = reasons.get(r, 0) + 1
        reasons_str = ", ".join(f"{k}: {v}" for k, v in sorted(reasons.items()))
        print(f"  Fallback details:   {reasons_str}")

    print("-" * 80)
    print(
        f"Latency:   Avg: {avg_lat:.1f}ms | P50: {p50_lat:.1f}ms | "
        f"P95: {p95_lat:.1f}ms | Max: {max_lat:.1f}ms"
    )
    print(
        f"Tokens:    Prompt: {tot_prompt} (Cached: {tot_cached}) | "
        f"Completion: {tot_completion} (Reasoning: {tot_reasoning})"
    )
    print(f"Est. Cost: ${tot_cost:.6f} USD")
    print("-" * 80)

    # Breakdown by mix
    mixes = sorted(set(s["mix"] for s in scores))
    print(
        f"{'Mix':<12} | {'Count':>5} | {'Pass %':>7} | {'Action %':>8} | "
        f"{'Fallbacks':>9} | {'Avg Lat':>9} | {'Cost ($)':>10}"
    )
    print("-" * 80)
    for m in mixes:
        m_scores = [s for s in scores if s["mix"] == m]
        m_cnt = len(m_scores)
        m_pass = sum(1 for s in m_scores if s["pass"])
        m_act = sum(1 for s in m_scores if s["action_ok"])
        m_fb = sum(1 for s in m_scores if s["used_fallback"])
        m_lat = sum(s["elapsed_ms"] for s in m_scores) / m_cnt
        m_cost = sum(s["cost_usd"] for s in m_scores)
        print(
            f"{m:<12} | {m_cnt:>5} | {m_pass / m_cnt * 100:>6.1f}% | "
            f"{m_act / m_cnt * 100:>7.1f}% | {m_fb:>9} | {m_lat:>7.1f}ms | "
            f"${m_cost:>9.6f}"
        )

    print_confusion_matrix(scores)
    print("=" * 80)


def save_results_csv(scores: list[dict[str, Any]], results_dir: Path) -> Optional[Path]:
    """Save detailed evaluation results to timestamped CSV."""
    if not scores:
        return None

    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = results_dir / f"llm_{timestamp}.csv"

    fieldnames = [
        "id",
        "run",
        "mix",
        "expected_action",
        "got_action",
        "expected_find",
        "got_find",
        "expected_which",
        "got_which",
        "action_ok",
        "find_ok",
        "which_ok",
        "text_cer",
        "review_flag",
        "pass",
        "used_fallback",
        "fallback_reason",
        "elapsed_ms",
        "prompt_tokens",
        "completion_tokens",
        "cached_tokens",
        "reasoning_tokens",
        "cost_usd",
        "notes",
    ]

    with open(csv_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in scores:
            row_dict = {k: s.get(k, "") for k in fieldnames}
            writer.writerow(row_dict)

    return csv_path


async def run_evaluation(
    csv_path: Path,
    only_id: Optional[str] = None,
    runs: int = 1,
    reasoning_effort: Optional[str] = None,
    show_failed: bool = False,
    results_dir: Path = RESULTS_DIR,
) -> list[dict[str, Any]]:
    """Run evaluation across CSV rows with warm-up call."""
    if not settings.META_API_KEY:
        print("Error: META_API_KEY is not configured in settings or environment.")
        return []

    rows = load_eval_rows(csv_path)
    if only_id:
        rows = [r for r in rows if r["id"].strip() == only_id.strip()]
        if not rows:
            print(f"No row found with id={only_id}")
            return []

    print("=" * 80)
    print("SPARK LLM EVALUATION")
    print(f"CSV Path:         {csv_path}")
    print(f"Rows to evaluate: {len(rows)} ({runs} run(s) each)")
    print(f"Reasoning effort: {reasoning_effort or settings.SPARK_REASONING_EFFORT}")
    if only_id:
        print(f"Filter:           id={only_id}")
    print("=" * 80)

    await init_llm_client()
    try:
        # Warm-up call discarded from statistics
        print("Running warm-up call...")
        await process("warm up", "", reasoning_effort=reasoning_effort)
        print("Warm-up complete. Starting benchmark...\n")

        all_scores: list[dict[str, Any]] = []

        for run_idx in range(1, runs + 1):
            if runs > 1:
                print(f"--- RUN {run_idx}/{runs} ---")

            for r in rows:
                row_id = r["id"].strip()
                mix = r.get("mix", "").strip()

                result = await process(
                    spoken_text=r["spoken_text"],
                    box_text=r["box_text"],
                    reasoning_effort=reasoning_effort,
                )

                score = score_row(r, result)
                score["run"] = run_idx
                all_scores.append(score)

                # Format single-line console output (numbers, reason codes, status)
                status_str = "PASS" if score["pass"] else "FAIL"
                fb_str = (
                    f" | fb={score['fallback_reason']}"
                    if score["used_fallback"]
                    else ""
                )
                cer_str = ""
                if score["text_cer"] is not None:
                    flag_note = (
                        f" [{score['review_flag']}]" if score["review_flag"] else ""
                    )
                    cer_str = f" | CER={score['text_cer'] * 100:.1f}%{flag_note}"

                tok_str = f"{score['prompt_tokens']}p+{score['completion_tokens']}c"
                print(
                    f"[{row_id:>2}] ({mix:<8}) exp={score['expected_action']:<7} "
                    f"got={score['got_action']:<7} | {status_str:<4} | "
                    f"{score['elapsed_ms']:5.0f}ms | {tok_str:>9}{fb_str}{cer_str}"
                )

                if show_failed and not score["pass"]:
                    print(
                        f"    [FAIL DETAILS] expected_find={score['expected_find']!r}, "
                        f"got_find={score['got_find']!r}, "
                        f"expected_which={score['expected_which']!r}, "
                        f"got_which={score['got_which']!r}"
                    )
                    print(f"    [SPARK TEXT] {score['got_text']}")
                    if score["used_fallback"]:
                        print(f"    [FALLBACK] reason={score['fallback_reason']}")

        print_summary_tables(all_scores)
        out_csv = save_results_csv(all_scores, results_dir)
        if out_csv:
            print(f"\nDetailed results saved to: {out_csv}")

        return all_scores

    finally:
        await close_llm_client()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark Spark LLM action model on test CSV."
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=str(DEFAULT_CSV_PATH),
        help="Path to evaluation CSV (default: eval/texttest.csv)",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Filter by specific row id (e.g. --only 5)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of evaluation runs per row (default: 1)",
    )
    parser.add_argument(
        "--reasoning-effort",
        type=str,
        default=None,
        choices=["none", "low", "medium", "high"],
        help="Override SPARK_REASONING_EFFORT setting",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        default=False,
        help="Print Spark's text for failed rows",
    )
    return parser.parse_args(argv)


async def async_main(argv: Optional[list[str]] = None) -> None:
    args = parse_args(argv)
    csv_path = Path(args.csv)
    if not csv_path.is_absolute() and not csv_path.exists():
        csv_path = BASE_DIR / csv_path

    await run_evaluation(
        csv_path=csv_path,
        only_id=args.only,
        runs=args.runs,
        reasoning_effort=args.reasoning_effort,
        show_failed=args.show,
    )


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
