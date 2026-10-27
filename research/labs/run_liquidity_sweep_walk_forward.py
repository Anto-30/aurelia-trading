"""Run research-only R_100 liquidity-sweep walk-forward on sealed snapshots.

This command aborts if data, manifest integrity, or verified costs are missing.
It never places orders and its output is never a release authorization.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from research.labs.freeze_r100_dataset import verify_manifest, parse_aware_datetime, sha256_file
from research.labs.liquidity_sweep_strategy import (
    OHLCBar, ResearchSignal, generate_research_signals,
)
from research.labs.liquidity_sweep_backtest import (
    BacktestConfig, run_walk_forward, load_verified_cost_config,
)

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False


def load_sealed_bars(
    path: Path,
    *,
    expected_sha256: str,
    expected_size: int,
    expected_rows: int,
) -> list[OHLCBar]:
    # Verify both before and after parsing to catch stale/corrupt snapshots and
    # ordinary time-of-check/time-of-use changes between manifest check and load.
    if not path.is_file():
        raise FileNotFoundError(f"SEALED_DATASET_MISSING:{path}")
    if path.stat().st_size != expected_size or sha256_file(path) != expected_sha256:
        raise ValueError(f"SEALED_DATASET_HASH_OR_SIZE_MISMATCH:{path}")
    bars: list[OHLCBar] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = [str(item).strip().lower() for item in (reader.fieldnames or [])]
        if not all(name in headers for name in ("datetime", "open", "high", "low", "close")):
            raise ValueError(f"SEALED_DATA_SCHEMA_INVALID:{path}")
        reader.fieldnames = headers
        for row in reader:
            bars.append(OHLCBar(
                timestamp_utc=parse_aware_datetime(row["datetime"]).isoformat().replace("+00:00", "Z"),
                open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]),
            ))
    if len(bars) != expected_rows:
        raise ValueError(f"SEALED_DATASET_ROW_COUNT_MISMATCH:{path}")
    if len(bars) < 20:
        raise ValueError(f"DATASET_TOO_SHORT:{path}")
    if path.stat().st_size != expected_size or sha256_file(path) != expected_sha256:
        raise ValueError(f"SEALED_DATASET_CHANGED_DURING_LOAD:{path}")
    return bars


def resolve_manifest_dataset(manifest_path: Path, record: dict[str, object]) -> Path:
    location = Path(str(record["path"]))
    if location.is_absolute():
        return location
    # Manifest paths are repository-relative.
    root = Path(__file__).resolve().parents[2]
    return root / location


def fold_signal_factory(context_15m: Sequence[OHLCBar], *, pivot_window: int, reclaim_window: int,
                        reward_risk: float, stop_buffer: float):
    def generate(train_bars: Sequence[OHLCBar], test_bars: Sequence[OHLCBar]) -> list[ResearchSignal]:
        offset = len(train_bars)
        combined = [*train_bars, *test_bars]
        candidates = generate_research_signals(
            combined,
            context_bars_15m=context_15m,
            pivot_window=pivot_window,
            reclaim_window=reclaim_window,
            reward_risk=reward_risk,
            stop_buffer=stop_buffer,
        )
        local: list[ResearchSignal] = []
        for signal in candidates:
            # Require the full setup and confirmation to be inside the test fold.
            # This keeps fold-local indices valid and avoids importing a setup
            # selected in the calibration window into the scored window.
            if signal.sweep_index < offset or signal.confirmation_index < offset:
                continue
            if signal.entry_index >= len(combined):
                continue
            local.append(replace(
                signal,
                sweep_index=signal.sweep_index - offset,
                reclaim_index=signal.reclaim_index - offset,
                confirmation_index=signal.confirmation_index - offset,
                entry_index=signal.entry_index - offset,
            ))
        return local
    return generate


def _current_git_commit(repo_root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root,
            check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("GIT_COMMIT_UNKNOWN:run from a clean checked-out repository") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/frozen/r100_dual_resolution_manifest.json")
    parser.add_argument("--costs", default="config/costs.yaml")
    parser.add_argument("--resolution", choices=("1m",), default="1m",
                        help="R_100 strategy entries are 1m; 15m is completed-candle context.")
    parser.add_argument("--train-window-days", type=int, default=90)
    parser.add_argument("--test-window-days", type=int, default=30)
    parser.add_argument("--initial-capital", type=float, default=100000.0,
                        help="Research accounting baseline only; not a sizing recommendation.")
    parser.add_argument("--quantity", type=float, default=1.0,
                        help="Fixed research units; live/contract sizing is not modeled.")
    parser.add_argument("--pivot-window", type=int, default=2)
    parser.add_argument("--reclaim-window", type=int, default=3)
    parser.add_argument("--reward-risk", type=float, choices=(2.0, 3.0), default=2.0)
    parser.add_argument("--stop-buffer", type=float, default=0.0)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = verify_manifest(manifest_path)
    if manifest.get("instrument") != "R_100":
        raise ValueError("DATASET_INSTRUMENT_MISMATCH")
    if manifest.get("qualification_allowed") is not False:
        raise ValueError("MANIFEST_QUALIFICATION_FLAG_MUST_REMAIN_FALSE")

    # Verified source-backed costs are mandatory for the decision-grade run.
    cost = load_verified_cost_config(args.costs, args.resolution)
    one_minute_record = manifest["datasets"]["1m"]
    fifteen_minute_record = manifest["datasets"]["15m"]
    one_minute = load_sealed_bars(
        resolve_manifest_dataset(manifest_path, one_minute_record),
        expected_sha256=str(one_minute_record["sha256"]),
        expected_size=int(one_minute_record["file_size_bytes"]),
        expected_rows=int(one_minute_record["row_count"]),
    )
    fifteen_minute = load_sealed_bars(
        resolve_manifest_dataset(manifest_path, fifteen_minute_record),
        expected_sha256=str(fifteen_minute_record["sha256"]),
        expected_size=int(fifteen_minute_record["file_size_bytes"]),
        expected_rows=int(fifteen_minute_record["row_count"]),
    )
    repo_root = Path(__file__).resolve().parents[2]
    git_commit = _current_git_commit(repo_root)
    if not git_commit:
        raise RuntimeError("GIT_COMMIT_UNKNOWN")
    if any(a.timestamp_utc >= b.timestamp_utc for a, b in zip(one_minute, one_minute[1:])):
        raise ValueError("1M_TIMESTAMP_ORDER_INVALID")
    if any(a.timestamp_utc >= b.timestamp_utc for a, b in zip(fifteen_minute, fifteen_minute[1:])):
        raise ValueError("15M_TIMESTAMP_ORDER_INVALID")

    expected_1m = int(manifest["datasets"]["1m"]["row_count"])
    expected_15m = int(manifest["datasets"]["15m"]["row_count"])
    if (len(one_minute), len(fifteen_minute)) != (expected_1m, expected_15m):
        raise ValueError("SEALED_DATASET_ROW_COUNT_MISMATCH")

    config = BacktestConfig(
        initial_capital=args.initial_capital,
        quantity=args.quantity,
        commission_per_side=float(cost["commission_per_unit_usd_per_side"]),
        slippage_bps=0.0,
        usd_per_point_per_unit=float(cost["usd_per_point_per_unit"]),
        spread_points=float(cost["spread_points"]),
        slippage_points=float(cost["slippage_points"]),
    )
    factory = fold_signal_factory(
        fifteen_minute,
        pivot_window=args.pivot_window,
        reclaim_window=args.reclaim_window,
        reward_risk=args.reward_risk,
        stop_buffer=args.stop_buffer,
    )
    folds = run_walk_forward(
        one_minute,
        factory,
        config,
        train_window=args.train_window_days * 1440,
        test_window=args.test_window_days * 1440,
    )

    output = {
        "schema": "aurelia.liquidity_sweep_walk_forward.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "python_version": sys.version.split()[0],
        "status": "RESEARCH_ONLY_NOT_QUALIFIED",
        "qualification_allowed": False,
        "capital_authority": False,
        "live_execution": False,
        "strategy": {
            "name": "liquidity_sweep_structural_confirmation",
            "pivot_window": args.pivot_window,
            "reclaim_window": args.reclaim_window,
            "reward_risk": args.reward_risk,
            "stop_buffer_points": args.stop_buffer,
        },
        "dataset_manifest": str(manifest_path),
        "dataset_hashes": {
            key: manifest["datasets"][key]["sha256"] for key in ("1m", "15m")
        },
        "costs": {
            "config_path": args.costs,
            "config_sha256": cost["cost_config_sha256"],
            "verified": True,
            "resolution": args.resolution,
            "spread_points": config.spread_points,
            "slippage_points_per_side": config.slippage_points,
            "commission_per_unit_usd_per_side": config.commission_per_side,
            "cost_source": cost["source"],
            "contract_type": cost["contract_type"],
            "pnl_model": cost["pnl_model"],
            "usd_per_point_per_unit": cost["usd_per_point_per_unit"],
            "economics_source": cost["economics_source"],
            "bar_price_basis": "MIDPOINT",
        },
        "execution_model": {
            "quantity": args.quantity,
            "capital": args.initial_capital,
            "bar_based": True,
            "stop_first_if_same_bar_hits_stop_and_target": True,
            "tick_precision": False,
            "risk_sizing_model": "NOT_IMPLEMENTED",
        },
        "fold_count": len(folds),
        "folds": folds,
        "promotion_blockers": [
            "Results are research-only and are not independent out-of-sample qualification.",
            "Prospective paper reconciliation and independent human review are still required.",
        ],
    }
    out_path = Path(args.output) if args.output else Path("results") / (
        "liquidity_sweep_walk_forward_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({
        "status": output["status"],
        "fold_count": len(folds),
        "output": str(out_path),
        "qualification_allowed": False,
        "total_trades": sum(int(fold["metrics"]["total_trades"]) for fold in folds),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
