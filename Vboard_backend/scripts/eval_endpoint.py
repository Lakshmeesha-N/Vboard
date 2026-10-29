import argparse
import csv
import io
import math
import time
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

# Project root: Vboard_backend
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_AUDIO_DIR = BASE_DIR / "eval" / "audio"
DEFAULT_RESULTS_DIR = BASE_DIR / "eval" / "results"
DEFAULT_URL = "http://127.0.0.1:8000/v1/process"


def estimate_muse_cost(duration_ms: int) -> float:
    """
    Calculate estimated Muse transcription cost.

    Muse bills whole seconds rounded down at $0.003 per minute ($0.00005 per sec).
    """
    whole_seconds = max(0, int(duration_ms // 1000))
    return whole_seconds * (0.003 / 60.0)


def compute_percentile(data: list[float], percentile: float) -> float:
    """
    Compute given percentile (0-100) using linear interpolation.
    """
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


def create_in_memory_wav(
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
    duration_s: float = 1.0,
    amplitude: float = 16000.0,
) -> bytes:
    """Generate in-memory WAV byte buffer without disk writes."""
    buf = io.BytesIO()
    num_frames = int(sample_rate * duration_s)

    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)

        frames = bytearray()
        for i in range(num_frames):
            val = (
                int(amplitude * math.sin(2 * math.pi * 440.0 * (i / sample_rate)))
                if amplitude > 0
                else 0
            )
            frame = val.to_bytes(2, byteorder="little", signed=True)
            frames.extend(frame * channels)

        wf.writeframes(bytes(frames))

    return buf.getvalue()


def run_error_checks(client: httpx.Client, url: str) -> None:
    """Run in-memory error checks to verify guardrails at endpoint."""
    print("\n--- Running Endpoint Guardrail Checks ---")

    # 1. Silent audio check (must return 400)
    silent_wav = create_in_memory_wav(duration_s=1.0, amplitude=0.0)
    files_silent = {"audio": ("silent.wav", silent_wav, "audio/wav")}
    r_silent = client.post(url, files=files_silent)
    status_silent = (
        "PASS" if r_silent.status_code == 400 else f"FAIL ({r_silent.status_code})"
    )
    print(f"  [1] Silent audio rejection (expect 400): {status_silent}")

    # 2. Stereo audio check (must return 400)
    stereo_wav = create_in_memory_wav(channels=2, duration_s=1.0)
    files_stereo = {"audio": ("stereo.wav", stereo_wav, "audio/wav")}
    r_stereo = client.post(url, files=files_stereo)
    status_stereo = (
        "PASS" if r_stereo.status_code == 400 else f"FAIL ({r_stereo.status_code})"
    )
    print(f"  [2] Stereo audio rejection (expect 400): {status_stereo}")

    # 3. 6 MB oversized payload check (must return 413)
    oversized_bytes = b"RIFF" + b"\x00" * (6 * 1024 * 1024)
    files_oversized = {"audio": ("oversized.wav", oversized_bytes, "audio/wav")}
    r_oversized = client.post(url, files=files_oversized)
    status_oversized = (
        "PASS"
        if r_oversized.status_code == 413
        else f"FAIL ({r_oversized.status_code})"
    )
    print(f"  [3] 6MB payload rejection (expect 413): {status_oversized}")
    print("-" * 40)


def evaluate_endpoint(
    url: str = DEFAULT_URL,
    audio_dir: Path = DEFAULT_AUDIO_DIR,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    lang: Optional[str] = None,
    only: Optional[str] = None,
    runs: int = 1,
) -> None:
    """Benchmark the running /v1/process endpoint across local audio samples."""
    if not audio_dir.exists():
        print(f"Error: Audio directory does not exist: {audio_dir}")
        return

    wav_files = sorted(audio_dir.glob("*.wav"))
    if only:
        wav_files = [f for f in wav_files if only in f.name]

    if not wav_files:
        print("No matching audio files found to evaluate.")
        return

    print("=" * 80)
    print("VBOARD ENDPOINT EVALUATION")
    print(f"Target URL:    {url}")
    print(f"Audio clips:   {len(wav_files)} files ({runs} run(s) each)")
    print(f"Language hint: {lang or 'None'}")
    if only:
        print(f"Filter:        '{only}'")
    print("=" * 80)

    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = results_dir / f"endpoint_{timestamp}.csv"

    # Use persistent httpx.Client for realistic HTTP benchmarking
    with httpx.Client(timeout=60.0) as client:
        # Pre-flight warm-up request
        print("\nSending warm-up request...")
        warmup_file = wav_files[0]
        with open(warmup_file, "rb") as f:
            warmup_bytes = f.read()

        warmup_data: dict[str, Any] = {"device_id": "eval_warmup"}
        if lang:
            warmup_data["languages"] = lang

        try:
            r_warmup = client.post(
                url,
                files={"audio": (warmup_file.name, warmup_bytes, "audio/wav")},
                data=warmup_data,
            )
        except Exception as exc:
            print(f"Error: Connection to {url} failed: {exc}")
            return

        if r_warmup.status_code != 200:
            print(
                f"Error: Warm-up failed with status {r_warmup.status_code}: "
                f"{r_warmup.text}"
            )
            return

        warmup_json = r_warmup.json()
        if "timings_ms" not in warmup_json or not warmup_json["timings_ms"]:
            print(
                "\n[WARNING] Server returned no timings_ms. "
                "Turn on the debug setting (DEBUG=True) on the server."
            )
            return

        stages_keys = list(warmup_json["timings_ms"].keys())
        print("Warm-up complete. Stages detected:", stages_keys)

        records: list[dict[str, Any]] = []

        for run_idx in range(1, runs + 1):
            print(f"\n--- Run {run_idx}/{runs} ---")
            for clip_idx, clip_path in enumerate(wav_files, start=1):
                with open(clip_path, "rb") as f:
                    clip_bytes = f.read()

                post_data: dict[str, Any] = {"device_id": f"eval_run_{run_idx}"}
                if lang:
                    post_data["languages"] = lang

                t0 = time.perf_counter()
                resp = client.post(
                    url,
                    files={"audio": (clip_path.name, clip_bytes, "audio/wav")},
                    data=post_data,
                )
                client_total_ms = (time.perf_counter() - t0) * 1000.0

                if resp.status_code != 200:
                    print(
                        f"[{clip_idx}/{len(wav_files)}] {clip_path.name}: "
                        f"Failed ({resp.status_code})"
                    )
                    continue

                resp_data = resp.json()
                t_stages = resp_data.get("timings_ms") or {}
                duration_ms = resp_data.get("audio_duration_ms", 0)
                read_ms = t_stages.get("read_ms", 0.0)
                guardrail_ms = t_stages.get("guardrail_ms", 0.0)
                stt_ms = t_stages.get("stt_ms", 0.0)
                server_total_ms = t_stages.get("total_ms", 0.0)
                network_overhead_ms = max(0.0, client_total_ms - server_total_ms)
                cost = estimate_muse_cost(duration_ms)

                # Check for unmeasured stages: is sum of stages far from server total?
                sum_stages = read_ms + guardrail_ms + stt_ms
                if abs(sum_stages - server_total_ms) > 20.0 and (
                    server_total_ms > 0
                    and abs(sum_stages - server_total_ms) / server_total_ms > 0.15
                ):
                    print(
                        f"  [Notice: {clip_path.name}] Unmeasured stage detected: "
                        f"sum={sum_stages:.1f}ms vs total={server_total_ms:.1f}ms"
                    )

                records.append({
                    "clip_name": clip_path.name,
                    "run_idx": run_idx,
                    "audio_duration_ms": duration_ms,
                    "client_total_ms": round(client_total_ms, 2),
                    "read_ms": round(read_ms, 2),
                    "guardrail_ms": round(guardrail_ms, 2),
                    "stt_ms": round(stt_ms, 2),
                    "server_total_ms": round(server_total_ms, 2),
                    "network_overhead_ms": round(network_overhead_ms, 2),
                    "estimated_cost_usd": round(cost, 6),
                })

                print(
                    f"[{clip_idx}/{len(wav_files)}] {clip_path.name:<20} "
                    f"Client: {client_total_ms:6.1f}ms | "
                    f"Read: {read_ms:5.1f}ms | "
                    f"Guard: {guardrail_ms:5.1f}ms | "
                    f"STT: {stt_ms:6.1f}ms | "
                    f"Net: {network_overhead_ms:5.1f}ms"
                )

        # Write results to CSV (strictly numbers only, NO audio or text)
        if records:
            fieldnames = [
                "clip_name",
                "run_idx",
                "audio_duration_ms",
                "client_total_ms",
                "read_ms",
                "guardrail_ms",
                "stt_ms",
                "server_total_ms",
                "network_overhead_ms",
                "estimated_cost_usd",
            ]
            with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)

            print(f"\nSaved run metrics to: {csv_path}")

            # Print summary statistics
            print("\n" + "=" * 80)
            print("BENCHMARK SUMMARY STATISTICS")
            print("=" * 80)

            stages = [
                ("read_ms", [r["read_ms"] for r in records]),
                ("guardrail_ms", [r["guardrail_ms"] for r in records]),
                ("stt_ms", [r["stt_ms"] for r in records]),
                ("server_total_ms", [r["server_total_ms"] for r in records]),
                ("network_overhead_ms", [r["network_overhead_ms"] for r in records]),
                ("client_total_ms", [r["client_total_ms"] for r in records]),
            ]

            client_avg = sum(r["client_total_ms"] for r in records) / len(records)

            header = (
                f"{'Metric / Stage':<22} {'Avg (ms)':<10} {'p50 (ms)':<10} "
                f"{'p95 (ms)':<10} {'Max (ms)':<10} {'% Client':<10}"
            )
            print(header)
            print("-" * 80)

            for name, vals in stages:
                avg_v = sum(vals) / len(vals)
                p50_v = compute_percentile(vals, 50.0)
                p95_v = compute_percentile(vals, 95.0)
                max_v = max(vals)
                pct = (avg_v / client_avg * 100.0) if client_avg > 0 else 0.0
                print(
                    f"{name:<22} {avg_v:<10.1f} {p50_v:<10.1f} "
                    f"{p95_v:<10.1f} {max_v:<10.1f} {pct:<9.1f}%"
                )

            total_cost = sum(r["estimated_cost_usd"] for r in records)
            print("-" * 80)
            print(f"Total Estimated Muse Cost: ${total_cost:.6f} USD")

        # Run in-memory error checks
        run_error_checks(client, url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark and evaluate the running Vboard /v1/process endpoint."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Target endpoint URL (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_AUDIO_DIR,
        help="Directory containing WAV files to test",
    )
    parser.add_argument(
        "--lang",
        default=None,
        help="Optional comma-separated language bias (e.g. 'Kannada,English')",
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Filter audio files by filename substring",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of evaluation runs over the clips (default: 1)",
    )

    args = parser.parse_args()
    evaluate_endpoint(
        url=args.url,
        audio_dir=args.dir,
        lang=args.lang,
        only=args.only,
        runs=args.runs,
    )


if __name__ == "__main__":
    main()
