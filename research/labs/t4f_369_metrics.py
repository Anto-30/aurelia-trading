"""Cost-aware T4F x 369 research journal metrics.

Metrics are descriptive. This module does not determine strategy validity,
statistical significance, or capital eligibility.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

REQUIRED_METRIC_COLUMNS = (
    "timestamp_utc", "risk_usd", "gross_pnl_usd",
    "commission_usd", "spread_cost_usd", "slippage_cost_usd",
)


def _validated_metric_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("TRADE_JOURNAL_EMPTY_OR_INVALID")
    missing = [column for column in REQUIRED_METRIC_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError("TRADE_JOURNAL_COLUMNS_MISSING:" + ",".join(missing))

    work = frame.copy()
    timestamps = pd.to_datetime(work["timestamp_utc"], utc=True, errors="coerce")
    if timestamps.isna().any():
        raise ValueError("TRADE_TIMESTAMP_INVALID")
    work["timestamp_utc"] = timestamps

    numeric_columns = [
        "risk_usd", "gross_pnl_usd", "commission_usd",
        "spread_cost_usd", "slippage_cost_usd",
    ]
    for column in numeric_columns:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    numbers = work[numeric_columns].to_numpy(dtype="float64")
    if not np.isfinite(numbers).all():
        raise ValueError("TRADE_METRICS_NON_FINITE_OR_NON_NUMERIC")
    if (work["risk_usd"] <= 0).any():
        raise ValueError("RISK_USD_MUST_BE_POSITIVE")
    cost_columns = ["commission_usd", "spread_cost_usd", "slippage_cost_usd"]
    if (work[cost_columns] < 0).any().any():
        raise ValueError("COSTS_MUST_BE_NON_NEGATIVE")
    if "candidate_id" in work.columns and work["candidate_id"].duplicated().any():
        raise ValueError("DUPLICATE_CANDIDATE_ID")

    return work.sort_values("timestamp_utc", kind="stable").reset_index(drop=True)


def _empty_metrics() -> dict[str, Any]:
    return {
        "total_trades": 0, "win_rate": None, "expectancy_net_r": None,
        "profit_factor_net": None, "max_drawdown_r": None,
        "gross_pnl_usd": 0.0, "total_costs_usd": 0.0, "net_pnl_usd": 0.0,
        "net_r_total": 0.0, "first_trade_utc": None, "last_trade_utc": None,
        "profit_factor_note": "No trades in this subset.",
    }


def calculate_performance_metrics(frame: pd.DataFrame) -> dict[str, Any]:
    """Calculate costs-after net metrics without mutating the caller's DataFrame."""
    if isinstance(frame, pd.DataFrame) and frame.empty:
        return _empty_metrics()
    work = _validated_metric_frame(frame)
    costs = work["commission_usd"] + work["spread_cost_usd"] + work["slippage_cost_usd"]
    net_pnl = work["gross_pnl_usd"] - costs
    net_r = net_pnl / work["risk_usd"]

    winners = net_pnl[net_pnl > 0]
    losers = net_pnl[net_pnl < 0]
    gross_profit = float(winners.sum())
    gross_loss = float(abs(losers.sum()))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    equity = np.concatenate(([0.0], net_r.cumsum().to_numpy(dtype="float64")))
    running_peak = np.maximum.accumulate(equity)
    drawdowns = equity - running_peak

    return {
        "total_trades": int(len(work)),
        "win_rate": float((net_r > 0).mean()),
        "expectancy_net_r": float(net_r.mean()),
        "profit_factor_net": profit_factor,
        "max_drawdown_r": float(drawdowns.min()),
        "gross_pnl_usd": float(work["gross_pnl_usd"].sum()),
        "total_costs_usd": float(costs.sum()),
        "net_pnl_usd": float(net_pnl.sum()),
        "net_r_total": float(net_r.sum()),
        "first_trade_utc": work["timestamp_utc"].iloc[0].isoformat(),
        "last_trade_utc": work["timestamp_utc"].iloc[-1].isoformat(),
        "profit_factor_note": None if profit_factor is not None else "No net losing trades; PF is undefined.",
    }


def evaluate_369_filter_ablation(frame: pd.DataFrame) -> dict[str, Any]:
    """Compare the same T4F candidate cohort with and without the 369 eligibility filter.

    Each row must be a fully evaluated hypothetical T4F setup using identical
    entry/stop/target/fill/cost rules. eligible_369 is the only treatment.
    """
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("CANDIDATE_COHORT_EMPTY_OR_INVALID")
    if "eligible_369" not in frame.columns:
        raise ValueError("ELIGIBLE_369_COLUMN_REQUIRED")
    if frame["eligible_369"].isna().any():
        raise ValueError("ELIGIBLE_369_MISSING")
    if not pd.api.types.is_bool_dtype(frame["eligible_369"]):
        raise ValueError("ELIGIBLE_369_MUST_BE_BOOLEAN")
    base = calculate_performance_metrics(frame)
    filtered = calculate_performance_metrics(frame.loc[frame["eligible_369"]].copy())
    return {
        "comparison_design": "SAME_T4F_CANDIDATE_COHORT_369_FILTER_ONLY",
        "structure_only_baseline": base,
        "t4f_369_filtered": filtered,
        "trade_count_retention": (
            filtered["total_trades"] / base["total_trades"]
            if base["total_trades"] else 0.0
        ),
        "interpretation_limit": (
            "Descriptive in-sample/out-of-sample metrics only. The comparison is not "
            "causal or statistically conclusive without a frozen protocol and untouched evaluation data."
        ),
    }
