#!/usr/bin/env python3
"""Run the frozen rule-based MSNR baseline on strictly verified R_100 1m candles.

Indicators/signals are vectorized before each simulation segment. Stateful execution
uses Numba-compiled iteration, not a Python loop over 1M bars. Only OHLC is used;
there is no volume/flow/profile/oscillator/ML logic, no broker authentication, and
no order-placement capability. Unit-normalized linear PnL is a research proxy until
a real linear contract and economics are independently documented.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd
from numba import njit

SCRIPT = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT.parents[1]
DEFAULT_MODEL = PROJECT_ROOT / "config" / "model_frozen.json"
REQUIRED_FIELDS = ("epoch", "open", "high", "low", "close")
TRADE_FIELDS = (
    "entry_epoch", "exit_epoch", "side", "entry_mid", "exit_mid", "atr_at_entry",
    "position_size_units", "risk_cash_units", "round_trip_cost_debited_at_entry",
    "gross_pnl_units", "net_pnl_units", "net_R", "holding_bars", "exit_reason_code",
)
REASON_NAMES = {1: "STOP", 2: "TARGET", 3: "END_OF_DATA"}
KILL_MESSAGE = "KILL CRITERIA MET: Baseline alpha insufficient. Halting HMM integration."

class SimulationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_verified_inputs(csv_path: Path, manifest_path: Path, verification_path: Path,
                         model_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for path in (csv_path, manifest_path, verification_path, model_path):
        if not path.is_file():
            raise SimulationError(f"Required input does not exist: {path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    model = json.loads(model_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "atos.deriv_history_manifest.v3":
        raise SimulationError("Unsupported or legacy source manifest schema.")
    if manifest.get("underlying_symbol") != "R_100" or manifest.get("timeframe") != "1m" or int(manifest.get("granularity_seconds", 0)) != 60:
        raise SimulationError("Only R_100 1m history is in scope for this simulator.")
    if manifest.get("endpoint") != "wss://api.derivws.com/trading/v1/options/ws/public":
        raise SimulationError("History was not fetched from the mandated current public WebSocket.")
    if manifest.get("authentication") != "none" or manifest.get("account_token_used") is not False:
        raise SimulationError("Manifest does not demonstrate unauthenticated data acquisition.")
    if verification.get("status") != "VERIFIED_CONTIGUOUS" or verification.get("simulator_eligible_under_strict_continuity") is not True:
        raise SimulationError("History verifier did not approve strict continuity; simulation is blocked.")
    data_hash = sha256_file(csv_path)
    if manifest.get("csv_sha256") != data_hash or verification.get("csv_sha256") != data_hash:
        raise SimulationError("CSV SHA-256 does not match both source manifest and verification report.")
    if model.get("schema") != "atos.msnr.baseline.v1" or model.get("underlying_symbol") != "R_100":
        raise SimulationError("Frozen model config missing/invalid or scoped to another underlying.")
    if model.get("parameters", {}).get("feature_execution_lag_bars") != 1:
        raise SimulationError("The one-bar signal lag is a non-negotiable model invariant.")
    if manifest.get("row_count") != verification.get("row_count"):
        raise SimulationError("Manifest and independent verifier disagree on row count.")
    expected = (datetime.fromisoformat(manifest["start_date_utc_inclusive"]).date(),
                datetime.fromisoformat(manifest["end_date_utc_exclusive"]).date())
    if (str(expected[0]), str(expected[1])) != ("2022-10-21", "2024-10-21"):
        raise SimulationError(
            "Historical range is not the frozen half-open UTC window "
            "[2022-10-21T00:00:00Z, 2024-10-21T00:00:00Z)."
        )
    if model.get("safety", {}).get("live_execution") != "BLOCKED" or model.get("safety", {}).get("final_execution_authorization") is not False:
        raise SimulationError("Model safety configuration is not fail-closed.")
    return manifest, verification, model


def add_features(frame: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
    """Vectorized causal features. No forward-fill or future candle references."""
    out = frame.copy()
    sweep_n = int(params["sweep_lookback_bars"])
    micro_n = int(params["microstructure_lookback_bars"])
    confirm_n = int(params["sweep_confirmation_bars"])
    atr_n = int(params["atr_period"])
    ma_n = int(params["regime_ma_period"])
    ma_slope_n = int(params["regime_ma_slope_lookback"])

    prev_close = out["close"].shift(1)
    true_range = pd.concat([
        out["high"] - out["low"],
        (out["high"] - prev_close).abs(),
        (out["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    # First row's high-low is causal; no future fill is used.
    if len(true_range):
        true_range.iloc[0] = out["high"].iloc[0] - out["low"].iloc[0]
    out["atr"] = true_range.rolling(atr_n, min_periods=atr_n).mean()

    prior_range_low = out["low"].rolling(sweep_n, min_periods=sweep_n).min().shift(1)
    prior_range_high = out["high"].rolling(sweep_n, min_periods=sweep_n).max().shift(1)
    sweep_long = (out["low"] < prior_range_low) & (out["close"] > prior_range_low) & (out["close"] > out["open"])
    sweep_short = (out["high"] > prior_range_high) & (out["close"] < prior_range_high) & (out["close"] < out["open"])
    recent_long_sweep = sweep_long.astype("int8").shift(1).rolling(confirm_n, min_periods=1).max().fillna(0) > 0
    recent_short_sweep = sweep_short.astype("int8").shift(1).rolling(confirm_n, min_periods=1).max().fillna(0) > 0

    prior_micro_high = out["high"].rolling(micro_n, min_periods=micro_n).max().shift(1)
    prior_micro_low = out["low"].rolling(micro_n, min_periods=micro_n).min().shift(1)
    bull_break = (out["close"] > prior_micro_high) & (out["close"].shift(1) <= prior_micro_high.shift(1)) & (out["close"] > out["open"])
    bear_break = (out["close"] < prior_micro_low) & (out["close"].shift(1) >= prior_micro_low.shift(1)) & (out["close"] < out["open"])

    out["regime_ma"] = out["close"].rolling(ma_n, min_periods=ma_n).mean()
    slope = out["regime_ma"] - out["regime_ma"].shift(ma_slope_n)
    out["regime"] = np.select(
        [(out["close"] > out["regime_ma"]) & (slope > 0),
         (out["close"] < out["regime_ma"]) & (slope < 0)],
        [1, -1], default=0,
    ).astype("int8")

    long_signal = recent_long_sweep & bull_break & (out["regime"] == 1)
    short_signal = recent_short_sweep & bear_break & (out["regime"] == -1)
    # Mutually exclusive signal encoding. Conflicting signals are blocked, not resolved post hoc.
    out["signal_at_close"] = np.select([long_signal & ~short_signal, short_signal & ~long_signal], [1, -1], default=0).astype("int8")
    # At row i execution can only read the fully completed signal/ATR at i-1.
    out["execution_signal"] = out["signal_at_close"].shift(1).fillna(0).astype("int8")
    out["execution_atr"] = out["atr"].shift(1)
    out["execution_regime"] = out["regime"].shift(1).fillna(0).astype("int8")
    return out


@njit(cache=True)
def _simulate_kernel(epoch, op, hi, lo, cl, signal, atr_lagged, process_start, global_offset,
                    side, entry_epoch, entry_mid, entry_atr, stop_price, target_price,
                    qty, risk_cash, entry_cost, entry_index, equity,
                    risk_fraction, multiplier, spread_price_points, slippage_bps, final_chunk):
    # Numeric trade matrix fields map to TRADE_FIELDS above; reason codes are 1/2/3.
    trades = np.zeros((len(epoch) + 2, len(TRADE_FIELDS)), dtype=np.float64)
    ntrades = 0
    error_code = 0
    for i in range(process_start, len(epoch)):
        # Convert the current index in this segment-plus-carry frame to a stable
        # absolute row index so holding duration remains correct across 90-day chunks.
        bar_index = global_offset + i - process_start
        exited = False
        if side != 0:
            stop_hit = (side == 1 and lo[i] <= stop_price) or (side == -1 and hi[i] >= stop_price)
            target_hit = (side == 1 and hi[i] >= target_price) or (side == -1 and lo[i] <= target_price)
            if stop_hit or target_hit:
                # If both barriers fall inside one OHLC bar, assume stop first.
                reason = 1 if stop_hit else 2
                if reason == 1:
                    if side == 1:
                        exit_mid = op[i] if op[i] < stop_price else stop_price
                    else:
                        exit_mid = op[i] if op[i] > stop_price else stop_price
                else:
                    if side == 1:
                        exit_mid = op[i] if op[i] > target_price else target_price
                    else:
                        exit_mid = op[i] if op[i] < target_price else target_price
                gross = side * (exit_mid - entry_mid) * qty * multiplier
                net = gross - entry_cost
                equity += gross
                trades[ntrades, 0] = entry_epoch
                trades[ntrades, 1] = epoch[i]
                trades[ntrades, 2] = side
                trades[ntrades, 3] = entry_mid
                trades[ntrades, 4] = exit_mid
                trades[ntrades, 5] = entry_atr
                trades[ntrades, 6] = qty
                trades[ntrades, 7] = risk_cash
                trades[ntrades, 8] = entry_cost
                trades[ntrades, 9] = gross
                trades[ntrades, 10] = net
                trades[ntrades, 11] = net / risk_cash if risk_cash > 0 else 0.0
                trades[ntrades, 12] = bar_index - entry_index + 1
                trades[ntrades, 13] = reason
                ntrades += 1
                side = 0
                entry_epoch = 0
                entry_mid = 0.0
                entry_atr = 0.0
                stop_price = 0.0
                target_price = 0.0
                qty = 0.0
                risk_cash = 0.0
                entry_cost = 0.0
                entry_index = 0
                exited = True
            if exited:
                continue  # no re-entry on the same candle that closed a position

        if side == 0:
            signal_side = int(signal[i])
            current_atr = atr_lagged[i]
            if signal_side != 0 and math.isfinite(current_atr) and current_atr > 0 and equity > 0:
                # Exact specified sizing formula; multiplier=1 only means normalized linear-price units.
                risk_cash = risk_fraction * equity
                qty = risk_cash / (current_atr * multiplier)
                if not math.isfinite(qty) or qty <= 0:
                    error_code = 1
                    break
                entry_mid = op[i]
                entry_atr = current_atr
                side = signal_side
                entry_epoch = epoch[i]
                entry_index = bar_index
                stop_price = entry_mid - side * entry_atr
                target_price = entry_mid + side * 2.0 * entry_atr
                # Round-trip cost is estimated and debited at entry, as directed.
                slip_price_per_fill = entry_mid * slippage_bps / 10000.0
                cost_price = spread_price_points + 2.0 * slip_price_per_fill
                entry_cost = cost_price * qty * multiplier
                if not math.isfinite(entry_cost) or entry_cost < 0 or entry_cost >= equity:
                    error_code = 2
                    break
                equity -= entry_cost
                # Entry candle's subsequent high/low can hit a stop or target. Stop wins ties.
                stop_hit = (side == 1 and lo[i] <= stop_price) or (side == -1 and hi[i] >= stop_price)
                target_hit = (side == 1 and hi[i] >= target_price) or (side == -1 and lo[i] <= target_price)
                if stop_hit or target_hit:
                    reason = 1 if stop_hit else 2
                    if reason == 1:
                        if side == 1:
                            exit_mid = op[i] if op[i] < stop_price else stop_price
                        else:
                            exit_mid = op[i] if op[i] > stop_price else stop_price
                    else:
                        if side == 1:
                            exit_mid = op[i] if op[i] > target_price else target_price
                        else:
                            exit_mid = op[i] if op[i] < target_price else target_price
                    gross = side * (exit_mid - entry_mid) * qty * multiplier
                    net = gross - entry_cost
                    equity += gross
                    trades[ntrades, 0] = entry_epoch
                    trades[ntrades, 1] = epoch[i]
                    trades[ntrades, 2] = side
                    trades[ntrades, 3] = entry_mid
                    trades[ntrades, 4] = exit_mid
                    trades[ntrades, 5] = entry_atr
                    trades[ntrades, 6] = qty
                    trades[ntrades, 7] = risk_cash
                    trades[ntrades, 8] = entry_cost
                    trades[ntrades, 9] = gross
                    trades[ntrades, 10] = net
                    trades[ntrades, 11] = net / risk_cash if risk_cash > 0 else 0.0
                    trades[ntrades, 12] = 1.0
                    trades[ntrades, 13] = reason
                    ntrades += 1
                    side = 0
                    entry_epoch = 0
                    entry_mid = 0.0
                    entry_atr = 0.0
                    stop_price = 0.0
                    target_price = 0.0
                    qty = 0.0
                    risk_cash = 0.0
                    entry_cost = 0.0
                    entry_index = 0
    if final_chunk and side != 0 and len(epoch) > process_start:
        i = len(epoch) - 1
        exit_mid = cl[i]
        gross = side * (exit_mid - entry_mid) * qty * multiplier
        net = gross - entry_cost
        equity += gross
        trades[ntrades, 0] = entry_epoch
        trades[ntrades, 1] = epoch[i]
        trades[ntrades, 2] = side
        trades[ntrades, 3] = entry_mid
        trades[ntrades, 4] = exit_mid
        trades[ntrades, 5] = entry_atr
        trades[ntrades, 6] = qty
        trades[ntrades, 7] = risk_cash
        trades[ntrades, 8] = entry_cost
        trades[ntrades, 9] = gross
        trades[ntrades, 10] = net
        trades[ntrades, 11] = net / risk_cash if risk_cash > 0 else 0.0
        end_bar_index = global_offset + len(epoch) - 1 - process_start
        trades[ntrades, 12] = end_bar_index - entry_index + 1
        trades[ntrades, 13] = 3
        ntrades += 1
        side = 0
    return (trades, ntrades, side, entry_epoch, entry_mid, entry_atr, stop_price, target_price,
            qty, risk_cash, entry_cost, entry_index, equity, error_code)


def iter_90_day_segments(csv_path: Path, start_epoch: int, end_exclusive: int,
                         granularity: int, csv_chunk_rows: int) -> Iterator[pd.DataFrame]:
    """Stream verified candles into non-overlapping 90-day segments."""
    segment_seconds = 90 * 86400
    current_end = min(start_epoch + segment_seconds, end_exclusive)
    pending = pd.DataFrame(columns=list(REQUIRED_FIELDS))
    for part in pd.read_csv(csv_path, usecols=list(REQUIRED_FIELDS), chunksize=csv_chunk_rows):
        for col in REQUIRED_FIELDS:
            part[col] = pd.to_numeric(part[col], errors="raise")
        part["epoch"] = part["epoch"].astype(np.int64)
        work = pd.concat([pending, part], ignore_index=True) if not pending.empty else part.reset_index(drop=True)
        while not work.empty and int(work["epoch"].max()) >= current_end:
            ready = work.loc[work["epoch"] < current_end].copy().reset_index(drop=True)
            pending = work.loc[work["epoch"] >= current_end].copy().reset_index(drop=True)
            if not ready.empty:
                yield ready
            current_end = min(current_end + segment_seconds, end_exclusive)
            work = pending
            pending = pd.DataFrame(columns=list(REQUIRED_FIELDS))
            if current_end >= end_exclusive:
                break
        if not work.empty:
            pending = work.reset_index(drop=True)
    if not pending.empty:
        pending = pending.loc[pending["epoch"] < end_exclusive].copy().reset_index(drop=True)
        if not pending.empty:
            yield pending


def resolve_git_commit(args_commit: str | None) -> tuple[str, str]:
    try:
        actual = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
                                check=True, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        actual = ""
    if actual:
        if args_commit and args_commit.lower() != actual.lower():
            raise SimulationError(f"Provided commit SHA {args_commit} differs from checked-out HEAD {actual}.")
        commit = actual
        source = "git working tree HEAD"
    else:
        commit = args_commit or ""
        source = "explicit repository commit SHA (source snapshot; no local .git directory)"
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise SimulationError("Exact 40-character repository commit SHA is required; no placeholder hashes allowed.")
    return commit.lower(), source


def write_ledger_records(ledger: Path, matrix: np.ndarray, count: int) -> int:
    """Append JSONL records and return a count without retaining trade dictionaries."""
    if count <= 0:
        return 0
    with ledger.open("a", encoding="utf-8") as f:
        for idx in range(count):
            row = matrix[idx]
            rec: dict[str, Any] = {}
            for j, name in enumerate(TRADE_FIELDS):
                value = row[j]
                if name in ("entry_epoch", "exit_epoch", "side", "holding_bars", "exit_reason_code"):
                    rec[name] = int(value)
                else:
                    rec[name] = float(value)
            rec["underlying_symbol"] = "R_100"
            rec["pnl_unit"] = "normalized linear price-PnL units; not a broker currency claim"
            rec["exit_reason"] = REASON_NAMES[int(rec["exit_reason_code"])]
            rec["transaction_cost_timing"] = "full estimated round-trip cost debited at simulated entry"
            f.write(json.dumps(rec, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n")
        f.flush()
    return count

def compute_metrics(trades: list[dict[str, Any]], initial_equity: float) -> dict[str, Any]:
    net = np.asarray([t["net_pnl_units"] for t in trades], dtype=np.float64)
    rvals = np.asarray([t["net_R"] for t in trades], dtype=np.float64)
    wins = net[net > 0]
    losses = net[net < 0]
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) else (float("inf") if len(wins) else None)
    equity = initial_equity
    peak = equity
    max_dd = 0.0
    for trade in trades:
        equity += float(trade["net_pnl_units"])
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak)
    return {
        "closed_trades": len(trades),
        "winning_trades": int((net > 0).sum()),
        "losing_trades": int((net < 0).sum()),
        "breakeven_trades": int((net == 0).sum()),
        "win_rate": float((net > 0).mean()) if len(net) else None,
        "profit_factor": pf if pf is None or math.isfinite(pf) else "infinite_no_losses",
        "net_expectancy_R": float(rvals.mean()) if len(rvals) else None,
        "median_net_R": float(np.median(rvals)) if len(rvals) else None,
        "net_pnl_units": float(net.sum()) if len(net) else 0.0,
        "estimated_round_trip_cost_units": float(sum(t["round_trip_cost_debited_at_entry"] for t in trades)),
        "max_closed_trade_equity_drawdown_fraction": max_dd,
        "initial_normalized_equity_units": initial_equity,
        "final_normalized_equity_units": initial_equity + float(net.sum()),
    }


def compute_metrics_from_ledger(ledger: Path, initial_equity: float) -> dict[str, Any]:
    """Stream the append-only trade ledger; retain only numeric PnL arrays."""
    net_values: list[float] = []
    r_values: list[float] = []
    total_cost = 0.0
    equity = initial_equity
    peak = initial_equity
    max_dd = 0.0
    with ledger.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                trade = json.loads(line)
                net = float(trade["net_pnl_units"])
                r_value = float(trade["net_R"])
                cost = float(trade["round_trip_cost_debited_at_entry"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise SimulationError(f"Invalid trade ledger record at line {line_no}; metrics aborted.") from exc
            if not all(math.isfinite(v) for v in (net, r_value, cost)) or cost < 0:
                raise SimulationError(f"Non-finite PnL/R/cost or negative costs at ledger line {line_no}.")
            net_values.append(net)
            r_values.append(r_value)
            total_cost += cost
            equity += net
            peak = max(peak, equity)
            if peak > 0:
                max_dd = max(max_dd, (peak - equity) / peak)
    net = np.asarray(net_values, dtype=np.float64)
    rvals = np.asarray(r_values, dtype=np.float64)
    wins = net[net > 0]
    losses = net[net < 0]
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) else (float("inf") if len(wins) else None)
    return {
        "closed_trades": len(net),
        "winning_trades": int((net > 0).sum()),
        "losing_trades": int((net < 0).sum()),
        "breakeven_trades": int((net == 0).sum()),
        "win_rate": float((net > 0).mean()) if len(net) else None,
        "profit_factor": pf if pf is None or math.isfinite(pf) else "infinite_no_losses",
        "net_expectancy_R": float(rvals.mean()) if len(rvals) else None,
        "median_net_R": float(np.median(rvals)) if len(rvals) else None,
        "net_pnl_units": float(net.sum()) if len(net) else 0.0,
        "estimated_round_trip_cost_units": total_cost,
        "max_closed_trade_equity_drawdown_fraction": max_dd,
        "initial_normalized_equity_units": initial_equity,
        "final_normalized_equity_units": equity,
    }


def evaluate_kill_rule(metrics: dict[str, Any]) -> tuple[bool, bool]:
    """Return (evaluated, met) using the exact frozen kill rule.

    When expectancy is non-positive, the kill rule is met even if PF is
    undefined for a zero-PnL-only sample. The string representation of an
    infinite PF (no losing trades) is above the 1.15 threshold.
    """
    closed = int(metrics.get("closed_trades", 0))
    expectancy = metrics.get("net_expectancy_R")
    pf = metrics.get("profit_factor")
    evaluated = closed > 0 and expectancy is not None and math.isfinite(float(expectancy))
    if not evaluated:
        return False, False
    expectancy_fails = float(expectancy) <= 0.0
    pf_fails = isinstance(pf, (int, float)) and math.isfinite(float(pf)) and float(pf) < 1.15
    return True, bool(expectancy_fails or pf_fails)


def run(args: argparse.Namespace) -> int:
    ledger = args.ledger.resolve()
    summary_path = args.summary.resolve()
    if ledger.exists() or summary_path.exists():
        raise SimulationError("Refusing to overwrite evidence. Choose a new ledger and summary path.")
    manifest, verification, model = load_verified_inputs(args.csv.resolve(), args.manifest.resolve(),
                                                          args.verification.resolve(), args.model.resolve())
    if not args.allow_unverified_linear_proxy:
        raise SimulationError("No independently verified Deriv linear contract/multiplier is available. Use --allow-unverified-linear-proxy only for explicitly unqualified research metrics.")
    pip_size_price = manifest.get("pip_size_price_from_active_symbols")
    if (isinstance(pip_size_price, bool) or not isinstance(pip_size_price, (float, int)) or
            not math.isfinite(float(pip_size_price)) or float(pip_size_price) <= 0):
        raise SimulationError("Cannot convert spread: current active_symbols.pip_size price unit is missing/invalid.")
    pip_size_price = float(pip_size_price)
    params = model["parameters"]
    risk_fraction = float(params["risk_fraction_of_equity"])
    multiplier = 1.0  # Explicit unit-normalized linear proxy, not actual broker economics.
    spread_price_points = float(params["spread_pips_full_round_trip"]) * pip_size_price
    slippage_bps = float(params["slippage_bps_per_fill"])
    seed = int(params["seed"])
    np.random.seed(seed)  # Explicit seed is recorded although this frozen model is deterministic.
    commit, commit_source = resolve_git_commit(args.git_commit)
    # Re-validate commit and hashes before any trade ledger is opened.
    csv_hash = sha256_file(args.csv.resolve())
    model_hash = sha256_file(args.model.resolve())
    if csv_hash != manifest["csv_sha256"] or csv_hash != verification["csv_sha256"]:
        raise SimulationError("Input data hash changed after verification.")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusively create append-only ledger before processing; partial files remain clearly unqualified.
    with ledger.open("x", encoding="utf-8") as f:
        f.write("")
    start_epoch = int(verification["first_epoch"])
    last_epoch = int(verification["last_epoch"])
    end_exclusive = last_epoch + int(manifest["granularity_seconds"])
    side = 0
    entry_epoch = 0
    entry_mid = entry_atr = stop_price = target_price = qty = risk_cash = entry_cost = 0.0
    entry_index = 0
    equity = float(params["initial_normalized_equity"])
    closed_trade_count = 0
    carried_raw = pd.DataFrame(columns=list(REQUIRED_FIELDS))
    processed_rows = 0
    segment_count = 0
    for raw_df in iter_90_day_segments(args.csv.resolve(), start_epoch, end_exclusive,
                                      int(manifest["granularity_seconds"]), int(params["data_chunk_csv_rows"])):
        segment_count += 1
        if raw_df.empty:
            continue
        if not carried_raw.empty:
            features_input = pd.concat([carried_raw, raw_df], ignore_index=True)
            process_start = len(carried_raw)
        else:
            features_input = raw_df.copy().reset_index(drop=True)
            process_start = 0
        features = add_features(features_input, params)
        arrays = [features[col].to_numpy() for col in ("epoch", "open", "high", "low", "close")]
        epoch_arr = np.asarray(arrays[0], dtype=np.int64)
        px = [np.asarray(a, dtype=np.float64) for a in arrays[1:]]
        sig = features["execution_signal"].to_numpy(dtype=np.int8)
        atr_lag = features["execution_atr"].to_numpy(dtype=np.float64)
        is_final = int(epoch_arr[-1]) >= last_epoch
        result = _simulate_kernel(epoch_arr, px[0], px[1], px[2], px[3], sig, atr_lag, process_start,
                                  processed_rows, side, entry_epoch, entry_mid, entry_atr, stop_price, target_price,
                                  qty, risk_cash, entry_cost, entry_index, equity,
                                  risk_fraction, multiplier, spread_price_points, slippage_bps, is_final)
        (matrix, ntrades, side, entry_epoch, entry_mid, entry_atr, stop_price, target_price,
         qty, risk_cash, entry_cost, entry_index, equity, error_code) = result
        if error_code:
            raise SimulationError(f"Compiled simulation kernel stopped with fail-closed error code {error_code}.")
        appended_count = write_ledger_records(ledger, matrix, int(ntrades))
        closed_trade_count += appended_count
        processed_rows += len(raw_df)
        print(f"[90-day segment {segment_count}] rows={len(raw_df)} carry={len(carried_raw)} trades_closed={ntrades} cumulative={closed_trade_count}", flush=True)
        # Exact explicit overlap and memory cleanup requirements.
        carried_raw = features_input.loc[:, list(REQUIRED_FIELDS)].tail(250).copy()
        del raw_df, features_input, features, arrays, epoch_arr, px, sig, atr_lag, matrix, result, appended_count
        gc.collect()
    if processed_rows != int(manifest["row_count"]):
        raise SimulationError(f"Streamed row count mismatch: processed {processed_rows}, manifest says {manifest['row_count']}.")
    metrics = compute_metrics_from_ledger(ledger, float(params["initial_normalized_equity"]))
    if metrics["closed_trades"] != closed_trade_count:
        raise SimulationError("Append-only ledger trade count changed between writes and metric pass.")
    pf = metrics["profit_factor"]
    expectancy = metrics["net_expectancy_R"]
    kill_rule_evaluated, kill = evaluate_kill_rule(metrics)
    summary = {
        "schema": "atos.msnr.empirical_validation.v1",
        "run_status": "COMPLETED_EXPLORATORY_PROXY_NOT_QUALIFIED",
        "qualification_status": "NOT_QUALIFIED",
        "underlying_symbol": "R_100", "timeframe": "1m",
        "data_range_utc": {"start_epoch": start_epoch, "end_epoch": last_epoch,
                            "start": datetime.fromtimestamp(start_epoch, timezone.utc).isoformat(),
                            "end": datetime.fromtimestamp(last_epoch, timezone.utc).isoformat()},
        "data_rows": processed_rows, "simulation_segments_90_days": segment_count,
        "data_csv_sha256": csv_hash,
        "repository_commit_sha": commit, "repository_commit_source": commit_source,
        "explicit_random_seed": seed, "numpy_seed_set": True,
        "model_config_sha256": model_hash,
        "manifest_sha256": sha256_file(args.manifest.resolve()),
        "verification_report_sha256": sha256_file(args.verification.resolve()),
        "model_parameters": params,
        "costs": {"spread_pips_full_round_trip": params["spread_pips_full_round_trip"],
                  "pip_size_price_from_active_symbols": pip_size_price,
                  "spread_price_points_full_round_trip": spread_price_points,
                  "spread_price_conversion_note": "2.0 assumed pips multiplied by captured active_symbols.pip_size price unit; not a measured broker spread",
                  "slippage_bps_per_fill": slippage_bps,
                  "slippage_cost_estimate": "5 bps per entry/exit side, both projected using entry price; assumed rather than observed",
                  "commission": "excluded per explicitly supplied assumptions; this is not a complete execution-cost model"},
        "linear_contract_status": "UNIT_NORMALIZED_LINEAR_PRICE_PROXY; no real Deriv contract or multiplier verified",
        "multiplier_used_for_sizing": multiplier,
        "signal_timing": "signal[i-1] executes at open[i]; ATR from i-1 sizes position",
        "features_precomputed_vectorized": True, "compiled_stateful_engine": "Numba JIT",
        "no_forward_fill_used": True, "simulated_volume_features": False,
        "trade_ledger_path": str(ledger), "trade_ledger_sha256": sha256_file(ledger),
        "metrics": metrics,
        "kill_rule": {"threshold_profit_factor": 1.15, "threshold_net_expectancy_R": 0.0,
                      "evaluated": kill_rule_evaluated,
                      "profit_factor_comparable": isinstance(pf, (int, float)) or pf == "infinite_no_losses",
                      "met": kill,
                      "message": KILL_MESSAGE if kill else None},
        "safety": {"live_execution": "BLOCKED", "final_execution_authorization": False,
                   "live_orders_submitted": False, "account_tokens_used": False,
                   "otp_used": False, "qualification_unlock": False},
        "limitations": [
            "This run requires --allow-unverified-linear-proxy and is exploratory; it does not establish an actually available Deriv linear contract.",
            "Multiplier 1.0 is a unit normalization only, not a Deriv contract multiplier; output PnL is not broker currency.",
            "Spread/slippage are user assumptions; commission is excluded and may make results optimistic.",
            "Historical OHLC validation and hashes do not validate out-of-sample performance or live executability.",
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    # Holy Trinity: data hash, repository commit, explicit random seed.
    print("HOLY_TRINITY_SHA256_DATA=" + csv_hash)
    print("HOLY_TRINITY_GIT_COMMIT_SHA=" + commit)
    print("HOLY_TRINITY_RANDOM_SEED=" + str(seed))
    print(json.dumps({"summary": str(summary_path), "trade_ledger": str(ledger), "metrics": metrics,
                      "kill_rule": summary["kill_rule"], "qualification_status": summary["qualification_status"]},
                     indent=2, allow_nan=False))
    if kill:
        print(KILL_MESSAGE)
        return 10
    if not kill_rule_evaluated:
        print("KILL RULE NOT EVALUATED: no closed trades or non-computable performance metrics; no statistical claim is made.")
        return 11
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--verification", required=True, type=Path)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--git-commit", help="Exact 40-character commit SHA, required when running outside a clone")
    parser.add_argument("--allow-unverified-linear-proxy", action="store_true",
                        help="Run R-metric research with multiplier=1 normalization; output remains NOT_QUALIFIED")
    args = parser.parse_args()
    try: return run(args)
    except (SimulationError, OSError, ValueError, KeyError) as exc:
        print(f"SIMULATION BLOCKED FAILED CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__": raise SystemExit(main())
