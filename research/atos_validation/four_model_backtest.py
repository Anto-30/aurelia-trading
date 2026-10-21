"""Matched four-model evaluation over audited trade-level outcomes.

Required columns: timestamp, strategy, r_gross, cost_r, fold.
Timestamps must be timezone-aware ISO-8601. cost_r is nonnegative realized execution
cost in R. The harness never invents strategy entries, fills, payouts, or costs.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd

MODEL_ORDER = ("alpha_beta_hmm", "gaussian_hmm", "ma_control", "unfiltered_msnr")
TIMESTAMP_TZ = re.compile(r"(?:[zZ]|[+-]\d{2}:?\d{2})$")


def summarize(r: pd.Series, folds: pd.Series) -> dict:
    values = r.to_numpy(dtype=float)
    if len(values) == 0:
        return {
            "expectancy_r": np.nan, "profit_factor": np.nan,
            "max_drawdown_r": np.nan, "sample_size": 0,
            "fold_stability": np.nan, "fold_count": 0,
        }
    if not np.isfinite(values).all():
        raise ValueError("non-finite net R values")
    gains = float(values[values > 0].sum())
    losses = float(-values[values < 0].sum())
    pf = gains / losses if losses > 0 else (float("inf") if gains > 0 else 0.0)
    equity = np.cumsum(values)
    peaks = np.maximum.accumulate(np.r_[0.0, equity])[1:]
    drawdown = float(np.min(equity - peaks))
    fold_means = pd.DataFrame({"net_r": values, "fold": folds.to_numpy()}).groupby("fold").net_r.mean()
    return {
        "expectancy_r": float(values.mean()),
        "profit_factor": float(pf),
        "max_drawdown_r": drawdown,
        "sample_size": len(values),
        "fold_stability": float(fold_means.var(ddof=1)) if len(fold_means) > 1 else np.nan,
        "fold_count": int(len(fold_means)),
    }


def load_trade_ledger(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"timestamp": "string"})
    required = {"timestamp", "strategy", "r_gross", "cost_r", "fold"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    if df.empty:
        raise ValueError("trade ledger is empty")
    raw_ts = df["timestamp"].astype("string").str.strip()
    if not bool(raw_ts.str.contains(TIMESTAMP_TZ, na=False).all()):
        raise ValueError("every timestamp must include an explicit timezone offset or Z")
    try:
        df["timestamp"] = pd.to_datetime(raw_ts, utc=True, errors="raise")
    except (ValueError, TypeError) as exc:
        raise ValueError("timestamp contains an invalid ISO-8601 date") from exc
    if df[["timestamp", "strategy", "fold"]].isna().any().any():
        raise ValueError("timestamp, strategy, and fold must not be null")
    df["strategy"] = df["strategy"].astype(str).str.strip()
    if (df["strategy"] == "").any():
        raise ValueError("strategy names must not be blank")
    unknown = set(df["strategy"].unique()) - set(MODEL_ORDER)
    if unknown:
        raise ValueError(f"unexpected model names: {sorted(unknown)}")
    df["r_gross"] = pd.to_numeric(df["r_gross"], errors="raise")
    df["cost_r"] = pd.to_numeric(df["cost_r"], errors="raise")
    numbers = df[["r_gross", "cost_r"]].to_numpy(dtype=float)
    if not np.isfinite(numbers).all():
        raise ValueError("gross returns and costs must be finite")
    if (df["cost_r"] < 0).any():
        raise ValueError("cost_r must be nonnegative realized execution cost in R")
    if df["fold"].astype(str).str.strip().eq("").any():
        raise ValueError("fold IDs must not be blank")
    if df.duplicated(["strategy", "timestamp"]).any():
        raise ValueError("duplicate timestamp within strategy; investigate duplicate trades")
    absent = set(MODEL_ORDER) - set(df["strategy"].unique())
    if absent:
        raise ValueError(f"all four matched strategies required; missing {sorted(absent)}")
    fold_sets = {name: set(df.loc[df.strategy == name, "fold"].unique()) for name in MODEL_ORDER}
    common_folds = fold_sets[MODEL_ORDER[0]]
    if any(fold_sets[name] != common_folds for name in MODEL_ORDER[1:]):
        raise ValueError("all four models must report the same WFA folds; encode zero-trade folds explicitly")
    df = df.sort_values(["timestamp", "strategy"]).reset_index(drop=True)
    df["net_r"] = df["r_gross"] - df["cost_r"]
    return df


def evaluate(path: str | Path) -> pd.DataFrame:
    df = load_trade_ledger(path)
    rows = []
    for name in MODEL_ORDER:
        sample = df[df.strategy == name]
        rows.append({"model": name, **summarize(sample.net_r, sample.fold)})
    return pd.DataFrame(rows).set_index("model").loc[list(MODEL_ORDER)].reset_index()


def evaluate_fold_metrics(path: str | Path) -> pd.DataFrame:
    """Return per-model, per-fold metrics so pooled performance cannot hide failed folds."""
    df = load_trade_ledger(path)
    rows = []
    for name in MODEL_ORDER:
        sample = df[df.strategy == name]
        for fold_id, fold_sample in sample.groupby("fold", sort=True):
            metrics = summarize(fold_sample.net_r, fold_sample.fold)
            rows.append({
                "model": name, "fold": fold_id,
                "expectancy_r": metrics["expectancy_r"],
                "profit_factor": metrics["profit_factor"],
                "max_drawdown_r": metrics["max_drawdown_r"],
                "sample_size": metrics["sample_size"],
            })
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trades_csv", help="audited trade ledger with realized costs and common WFA fold IDs")
    parser.add_argument("--out", default="four_model_metrics.csv")
    parser.add_argument("--fold-out", default="four_model_fold_metrics.csv")
    args = parser.parse_args()
    aggregate = evaluate(args.trades_csv)
    fold_metrics = evaluate_fold_metrics(args.trades_csv)
    aggregate.to_csv(args.out, index=False)
    fold_metrics.to_csv(args.fold_out, index=False)
    print("FOUR_MODEL_EVALUATION=COMPLETED")
    print(f"TRADE_LEDGER_SHA256={hashlib.sha256(Path(args.trades_csv).read_bytes()).hexdigest()}")
    print(f"AGGREGATE_METRICS_PATH={args.out}")
    print(f"FOLD_METRICS_PATH={args.fold_out}")
    print(aggregate.to_string(index=False))
    print("MODEL_PERFORMANCE_CLAIMED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
