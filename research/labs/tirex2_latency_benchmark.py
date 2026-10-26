"""Benchmark TiRex-2 inference latency on aligned historical price contexts.

This script makes no broker/API calls and does not emit trading decisions. It
reports model-load, first-call, and warmed end-to-end forecast timings. It is
intended to run on the actual proposed deployment hardware with an immutable
model revision and an explicitly chosen latency budget.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from research.labs.tirex2_synthetic_coupling import load_series_csv, sha256_file


def percentile_ms(values: Iterable[float], quantile: float) -> float:
    """Nearest-rank percentile with deterministic, dependency-free semantics."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("cannot summarize an empty latency sample")
    if not 0 < quantile <= 1:
        raise ValueError("quantile must be in (0, 1]")
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def summarize_latencies(values: Iterable[float]) -> dict[str, float | int]:
    samples = [float(value) for value in values]
    if not samples or any(not math.isfinite(v) or v < 0 for v in samples):
        raise ValueError("latencies must be a non-empty set of finite non-negative values")
    return {
        "count": len(samples),
        "min_ms": min(samples),
        "mean_ms": statistics.fmean(samples),
        "p50_ms": percentile_ms(samples, 0.50),
        "p95_ms": percentile_ms(samples, 0.95),
        "p99_ms": percentile_ms(samples, 0.99),
        "max_ms": max(samples),
    }


MIN_P99_SAMPLE_COUNT = 1000


def is_immutable_commit_sha(revision: str | None) -> bool:
    """Return true only for a full 40-character hexadecimal model commit SHA."""
    if revision is None or len(revision) != 40:
        return False
    try:
        int(revision, 16)
    except ValueError:
        return False
    return True


def latency_verdict(
    summary: dict[str, float | int],
    budget_ms: float | None,
    *,
    model_revision_pinned: bool = False,
) -> str:
    """Fail closed when latency evidence lacks a frozen budget, SHA pin, or sample count."""
    if budget_ms is None:
        return "NOT_EVALUATED_NO_FROZEN_BUDGET"
    if not math.isfinite(budget_ms) or budget_ms <= 0:
        raise ValueError("latency budget must be positive and finite")
    if not model_revision_pinned:
        return "NOT_EVALUATED_UNPINNED_MODEL_REVISION"
    if int(summary.get("count", 0)) < MIN_P99_SAMPLE_COUNT:
        return "NOT_EVALUATED_INSUFFICIENT_SAMPLES"
    return "PASS" if float(summary["p99_ms"]) <= budget_ms else "FAIL"


def _sync_device(torch, device: str) -> None:
    if device.startswith("cuda"):
        torch.cuda.synchronize(device)
    elif device == "mps" and hasattr(torch, "mps") and hasattr(torch.mps, "synchronize"):
        torch.mps.synchronize()


def _hardware_metadata(torch, device: str) -> dict[str, object]:
    details: dict[str, object] = {
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
        "python_version": platform.python_version(),
        "torch_version": getattr(torch, "__version__", "unknown"),
        "device": device,
    }
    if device.startswith("cuda") and torch.cuda.is_available():
        details["accelerator_name"] = torch.cuda.get_device_name(device)
    elif device == "mps" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        details["accelerator_name"] = "Apple Metal Performance Shaders"
    else:
        details["accelerator_name"] = "CPU or unavailable accelerator"
    return details


def _load_recent_aligned_contexts(series, symbols: list[str], context_length: int) -> tuple[list[list[float]], list[float]]:
    contexts: list[list[float]] = []
    reference_timestamps: list[float] | None = None
    for symbol in symbols:
        if symbol not in series:
            raise ValueError(f"requested symbol is not present in CSV: {symbol}")
        data = series[symbol]
        if len(data) < context_length:
            raise ValueError(f"symbol {symbol} has {len(data)} observations; {context_length} are required")
        timestamps = [float(value) for value in data.timestamps[-context_length:]]
        context = [float(value) for value in data.values[-context_length:]]
        if reference_timestamps is None:
            reference_timestamps = timestamps
        elif timestamps != reference_timestamps:
            raise ValueError(
                "multivariate latency mode requires exactly aligned timestamps for every selected symbol; "
                "the benchmark will not fabricate alignment"
            )
        contexts.append(context)
    return contexts, (reference_timestamps or [])


def _load_model(model_id: str, device: str, compile_model: bool, revision: str | None):
    try:
        import torch
        from tirex2 import TimeseriesType, load_model
    except ImportError as exc:
        raise RuntimeError(
            "TiRex-2 benchmark dependencies are missing. Install the optional extra: pip install '.[tirex2]'"
        ) from exc
    hf_kwargs = {"revision": revision} if revision else None
    model = load_model(model_id, device=device, compile=compile_model, hf_kwargs=hf_kwargs)
    return torch, TimeseriesType, model


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Price CSV with timestamp,symbol,close columns by default")
    parser.add_argument("--symbols", default="", help="Comma-separated aligned series; one series for univariate mode")
    parser.add_argument("--variates", type=int, default=1, help="Used only when --symbols is empty")
    parser.add_argument("--timestamp-column", default="timestamp")
    parser.add_argument("--series-column", default="symbol")
    parser.add_argument("--value-column", default="close")
    parser.add_argument("--context-length", type=int, default=128)
    parser.add_argument("--prediction-length", type=int, default=1)
    parser.add_argument("--device", choices=("cpu", "cuda", "mps"), default="cpu")
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--runs", type=int, default=MIN_P99_SAMPLE_COUNT)
    parser.add_argument("--latency-budget-ms", type=float, default=None,
                        help="Pre-registered p99 budget; if omitted no PASS/FAIL verdict is issued")
    parser.add_argument("--model-id", default="NX-AI/TiRex-2")
    parser.add_argument("--revision", default=None, help="Full 40-character Hugging Face model commit SHA required for a p99 PASS")
    parser.add_argument("--compile", action="store_true", help="Include compilation settings; first-call time is reported separately")
    parser.add_argument("--expected-interval-seconds", type=float, default=60.0,
                        help="Set 900 for 15-minute bars; use 0 to disable strict interval checks")
    parser.add_argument("--output", default="", help="Optional new JSON output path; existing paths are not overwritten")
    args = parser.parse_args(argv)
    interval = None if args.expected_interval_seconds == 0 else args.expected_interval_seconds

    data_load_started = time.perf_counter_ns()
    series = load_series_csv(
        args.csv,
        timestamp_column=args.timestamp_column,
        series_column=args.series_column,
        value_column=args.value_column,
        expected_interval_seconds=interval,
    )
    symbols = [part.strip() for part in args.symbols.split(",") if part.strip()] if args.symbols else []
    if not symbols:
        if args.variates < 1:
            parser.error("--variates must be positive")
        symbols = sorted(series)[:args.variates]
    if not args.symbols and len(symbols) != args.variates:
        parser.error("input CSV does not contain enough distinct series for --variates")
    if len(symbols) < 1 or len(set(symbols)) != len(symbols) or any(symbol not in series for symbol in symbols):
        parser.error("selected symbols must exist in the input CSV and must be unique")
    if args.runs < 1 or args.warmup < 0 or args.context_length < 1 or args.prediction_length < 1:
        parser.error("runs/context/prediction length must be positive; warmup must be non-negative")
    contexts, aligned_timestamps = _load_recent_aligned_contexts(series, symbols, args.context_length)
    data_load_ms = (time.perf_counter_ns() - data_load_started) / 1_000_000

    model_load_started = time.perf_counter_ns()
    torch, TimeseriesType, model = _load_model(args.model_id, args.device, args.compile, args.revision)
    model_load_ms = (time.perf_counter_ns() - model_load_started) / 1_000_000

    def make_input():
        # TiRex-2 requires [num_variates, context_length], including univariate V=1.
        return TimeseriesType(target=torch.as_tensor(contexts, dtype=torch.float32),
                              past_covariates=None, future_covariates=None)

    def forecast_once(timeseries=None):
        item = make_input() if timeseries is None else timeseries
        with torch.inference_mode():
            result = model.forecast([item], prediction_length=args.prediction_length, output_type="numpy")
        _sync_device(torch, args.device)
        return result

    first_input = make_input()
    input_start = time.perf_counter_ns()
    make_input()
    input_construction_ms = (time.perf_counter_ns() - input_start) / 1_000_000
    _sync_device(torch, args.device)
    first_start = time.perf_counter_ns()
    forecast_once(first_input)
    first_call_ms = (time.perf_counter_ns() - first_start) / 1_000_000

    for _ in range(args.warmup):
        forecast_once()
    durations = []
    for _ in range(args.runs):
        _sync_device(torch, args.device)
        begin = time.perf_counter_ns()
        forecast_once()
        durations.append((time.perf_counter_ns() - begin) / 1_000_000)

    summary = summarize_latencies(durations)
    report = {
        "schema": "aurelia.tirex2.latency-benchmark.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model_id": args.model_id,
        "model_revision": args.revision or "UNPINNED_MUTABLE_DEFAULT",
        "model_revision_is_immutable_commit_sha": is_immutable_commit_sha(args.revision),
        "minimum_warmed_samples_for_p99_verdict": MIN_P99_SAMPLE_COUNT,
        "device": args.device,
        "compile_enabled": args.compile,
        "symbols": symbols,
        "context_length": args.context_length,
        "prediction_length": args.prediction_length,
        "input_interval_seconds": interval,
        "input_csv_sha256": sha256_file(args.csv),
        "context_start_ts": aligned_timestamps[0] if aligned_timestamps else None,
        "context_end_ts": aligned_timestamps[-1] if aligned_timestamps else None,
        "input_data_load_ms": data_load_ms,
        "model_load_ms": model_load_ms,
        "input_construction_single_sample_ms": input_construction_ms,
        "first_forecast_call_ms_including_warmup_or_compile": first_call_ms,
        "warmup_runs": args.warmup,
        "warmed_runs": args.runs,
        "warmed_end_to_end_latency": summary,
        "latency_budget_ms": args.latency_budget_ms,
        "latency_verdict_based_on_p99": latency_verdict(
            summary,
            args.latency_budget_ms,
            model_revision_pinned=is_immutable_commit_sha(args.revision),
        ),
        "hardware": _hardware_metadata(torch, args.device),
        "measurement_scope": "input-object-construction plus local model forecast; excludes Deriv network/API, strategy, Layer 6, and broker latency",
        "broker_calls": 0,
        "live_execution_attempted": False,
        "promotion_status": "RESEARCH_ONLY_NOT_LAYER9_INTEGRATED",
    }
    output_text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        output_path = Path(args.output)
        if output_path.exists():
            raise FileExistsError(f"refusing to overwrite benchmark report: {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
    print(output_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
