"""Research-only walk-forward test for a Deriv tick-momentum proxy.

This module does not connect to a broker or submit/manage orders. It tests a
price-behaviour hypothesis on caller-supplied OHLCV data. For Deriv synthetics,
volume is treated as tick-volume proxy and CVD is NOT true bid/ask delta.

CLI:
    python -m research.labs.deriv_tick_momentum_absorption \
        --csv R75_6months_1min.csv --out wf_deriv --contract-type all

Only NumPy and pandas are required. Payoff models are screening approximations,
not substitutes for contract-specific quote/fill data.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
ContractType = Literal["CFD_PROXY", "MULTIPLIER_PROXY", "RISE_FALL_PROXY"]

SIGNAL_GRID: dict[str, list[float | int]] = {
    "cvd_lookback": [3, 5, 8],
    "atr_mult": [1.0, 1.5],
    "loc_tol_atr": [0.20, 0.40],
    "mag_mult": [1.0, 2.0],
    "vol_mult": [1.0, 1.5],
}


@dataclass(frozen=True)
class Config:
    """Inputs are assumptions unless confirmed from the data/contract quote."""
    contract_type: ContractType = "CFD_PROXY"
    vp_lookback: int = 200
    vp_bins: int = 120
    va_pct: float = 0.70
    atr_period: int = 14
    atr_ref: int = 50
    vol_ref: int = 20
    stop_buffer_atr: float = 0.25
    rr: float = 2.0
    max_hold: int = 30
    rf_duration_bars: int = 5
    payout_pct: float = 0.90
    multiplier: float = 10.0
    stake: float = 1.0
    equity: float = 1000.0
    risk_fraction: float = 0.005
    tick_size: float = 0.01
    spread_ticks: float = 1.0
    slippage_ticks: float = 0.5
    commission_bps: float = 0.0
    multiplier_commission_cash: float = 0.0
    is_bars: int = 20_000
    oos_bars: int = 5_000
    min_is_trades: int = 20
    min_oos_trades: int = 100
    min_profit_factor: float = 1.30
    min_expectancy_r: float = 0.15
    max_drawdown_r: float = 10.0
    min_positive_fold_share: float = 0.60

    def validate(self) -> None:
        if self.vp_lookback < 20 or self.vp_bins < 10:
            raise ValueError("vp_lookback must be >=20 and vp_bins >=10")
        if not 0.50 <= self.va_pct < 1.0:
            raise ValueError("va_pct must be in [0.50, 1.0)")
        if min(self.atr_period, self.atr_ref, self.vol_ref) < 2:
            raise ValueError("ATR and volume reference windows must be >=2")
        if self.stop_buffer_atr <= 0 or self.rr <= 0 or self.max_hold < 1:
            raise ValueError("stop buffer, RR and max_hold must be positive")
        if self.rf_duration_bars < 1 or not 0 < self.payout_pct < 10:
            raise ValueError("invalid Rise/Fall proxy duration or payout_pct")
        if min(self.multiplier, self.stake, self.equity, self.tick_size) <= 0:
            raise ValueError("multiplier, stake, equity and tick_size must be positive")
        if not 0 < self.risk_fraction <= 0.02:
            raise ValueError("risk_fraction must be in (0, 0.02]")
        if min(self.spread_ticks, self.slippage_ticks, self.commission_bps,
               self.multiplier_commission_cash) < 0:
            raise ValueError("friction and commissions cannot be negative")
        if self.is_bars < 100 or self.oos_bars < 50 or self.min_is_trades < 1:
            raise ValueError("IS/OOS windows or minimum trade count are too small")


def load_data(path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load and validate timestamp,open,high,low,close,volume CSV data."""
    raw = pd.read_csv(path)
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = sorted(set(required) - set(raw.columns))
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    raw_count = len(raw)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True, errors="coerce")
    for col in ("open", "high", "low", "close", "volume"):
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    bad_values = int(raw[required].isna().any(axis=1).sum())
    raw = raw.dropna(subset=required).copy()
    duplicates = int(raw.duplicated(subset=["timestamp"], keep="last").sum())
    raw = raw.drop_duplicates(subset=["timestamp"], keep="last")
    raw = raw.sort_values("timestamp").set_index("timestamp")
    finite = np.isfinite(raw[["open", "high", "low", "close", "volume"]].to_numpy()).all(axis=1)
    valid_ohlc = (
        (raw["high"] >= raw[["open", "close"]].max(axis=1))
        & (raw["low"] <= raw[["open", "close"]].min(axis=1))
        & (raw["high"] >= raw["low"])
        & (raw["volume"] >= 0)
    )
    invalid_ohlc = int((~(valid_ohlc & finite)).sum())
    raw = raw.loc[valid_ohlc & finite].copy()
    if raw.empty:
        raise ValueError("No valid OHLCV rows remain after validation")
    step_seconds = raw.index.to_series().diff().dt.total_seconds().dropna()
    median_step = float(step_seconds.median()) if len(step_seconds) else None
    gaps_3x = int((step_seconds > 3 * median_step).sum()) if median_step and median_step > 0 else 0
    report: dict[str, Any] = {
        "source_path": str(path),
        "raw_rows": raw_count,
        "valid_rows": len(raw),
        "rows_with_missing_or_unparseable_fields_dropped": bad_values,
        "duplicate_timestamps_dropped": duplicates,
        "invalid_or_nonfinite_ohlc_rows_dropped": invalid_ohlc,
        "start_utc": raw.index.min().isoformat(),
        "end_utc": raw.index.max().isoformat(),
        "median_bar_spacing_seconds": median_step,
        "gaps_over_3x_median_spacing": gaps_3x,
        "volume_semantics": "tick-volume proxy for Deriv synthetics; not traded capital",
    }
    if gaps_3x:
        report["warning"] = "Time gaps detected. Gaps were not filled or forward-imputed."
    return raw, report


def _volume_profile_for_window(window: pd.DataFrame, bins: int, va_pct: float) -> tuple[float, float] | None:
    """Approximate value area by allocating each bar's volume over its low-high bins."""
    lo, hi = float(window["low"].min()), float(window["high"].max())
    if not hi > lo:
        return None
    edges = np.linspace(lo, hi, bins + 1)
    lows = window["low"].to_numpy(dtype=float)
    highs = window["high"].to_numpy(dtype=float)
    volumes = window["volume"].to_numpy(dtype=float)
    b_lo = np.clip(np.searchsorted(edges, lows, side="right") - 1, 0, bins - 1)
    b_hi = np.clip(np.searchsorted(edges, highs, side="right") - 1, 0, bins - 1)
    weights = volumes / (b_hi - b_lo + 1)
    diff = np.zeros(bins + 1, dtype=float)
    np.add.at(diff, b_lo, weights)
    np.add.at(diff, b_hi + 1, -weights)
    profile = np.cumsum(diff)[:bins]
    total = float(profile.sum())
    if not math.isfinite(total) or total <= 0:
        return None
    poc = int(np.argmax(profile))
    left = right = poc
    accepted, target = float(profile[poc]), total * va_pct
    while accepted < target and (left > 0 or right < bins - 1):
        lv = float(profile[left - 1]) if left > 0 else -1.0
        rv = float(profile[right + 1]) if right < bins - 1 else -1.0
        if rv >= lv:  # deterministic upward tie-break
            right += 1
            accepted += float(profile[right])
        else:
            left -= 1
            accepted += float(profile[left])
    return float(edges[left]), float(edges[right + 1])


def build_profile(df: pd.DataFrame, cfg: Config) -> tuple[np.ndarray, np.ndarray]:
    """For signal bar i, use [i-lookback, i); the signal bar itself is excluded."""
    vah, val = np.full(len(df), np.nan), np.full(len(df), np.nan)
    for i in range(cfg.vp_lookback, len(df)):
        levels = _volume_profile_for_window(df.iloc[i-cfg.vp_lookback:i], cfg.vp_bins, cfg.va_pct)
        if levels is not None:
            val[i], vah[i] = levels
    return vah, val


def build_base(df: pd.DataFrame, cfg: Config, vah: np.ndarray, val: np.ndarray) -> dict[str, Any]:
    close = df["close"].astype(float)
    prev = close.shift(1)
    tr = pd.concat([
        df["high"] - df["low"], (df["high"] - prev).abs(),
        (df["low"] - prev).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/cfg.atr_period, adjust=False, min_periods=cfg.atr_period).mean()
    atr_ref = atr.rolling(cfg.atr_ref, min_periods=cfg.atr_ref).median()
    vol_ref = df["volume"].rolling(cfg.vol_ref, min_periods=cfg.vol_ref).mean()
    # Price-direction x supplied bar volume is a momentum proxy, NOT trade-side delta.
    delta = np.sign(close.diff()).fillna(0.0) * df["volume"].astype(float)
    cvd = delta.cumsum()
    mad = delta.abs().rolling(20, min_periods=20).mean()
    atr_a = atr.to_numpy(dtype=float)
    safe_atr = np.where(atr_a > 0, atr_a, np.nan)
    lows, highs = df["low"].to_numpy(dtype=float), df["high"].to_numpy(dtype=float)
    valid = (
        np.isfinite(atr_a) & np.isfinite(atr_ref.to_numpy(dtype=float))
        & np.isfinite(vol_ref.to_numpy(dtype=float)) & np.isfinite(mad.to_numpy(dtype=float))
        & np.isfinite(vah) & np.isfinite(val) & (atr_a > 0)
        & (mad.to_numpy(dtype=float) > 0)
    )
    return {
        "index": df.index, "o": df["open"].to_numpy(dtype=float),
        "h": highs, "l": lows, "c": close.to_numpy(dtype=float),
        "v": df["volume"].to_numpy(dtype=float), "atr": atr_a,
        "atr_ref": atr_ref.to_numpy(dtype=float), "vol_ref": vol_ref.to_numpy(dtype=float),
        "delta": delta.to_numpy(dtype=float), "cvd": cvd.to_numpy(dtype=float),
        "mad": mad.to_numpy(dtype=float), "vah": vah, "val": val,
        "dist_val_atr": np.abs(lows-val)/safe_atr,
        "dist_vah_atr": np.abs(highs-vah)/safe_atr, "valid": valid,
    }


def precompute_divergences(base: dict[str, Any]) -> dict[int, dict[str, np.ndarray]]:
    out: dict[int, dict[str, np.ndarray]] = {}
    cvd, lows, highs = pd.Series(base["cvd"]), pd.Series(base["l"]), pd.Series(base["h"])
    for k in (int(x) for x in SIGNAL_GRID["cvd_lookback"]):
        cvd_min = cvd.shift(1).rolling(k, min_periods=k).min().to_numpy()
        cvd_max = cvd.shift(1).rolling(k, min_periods=k).max().to_numpy()
        low_min = lows.shift(1).rolling(k, min_periods=k).min().to_numpy()
        high_max = highs.shift(1).rolling(k, min_periods=k).max().to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            mag_l = (cvd_min - base["cvd"]) / base["mad"]
            mag_s = (base["cvd"] - cvd_max) / base["mad"]
        mag_l = np.where(base["mad"] > 0, mag_l, -np.inf)
        mag_s = np.where(base["mad"] > 0, mag_s, -np.inf)
        out[k] = {
            "long_base": (base["cvd"] < cvd_min) & (base["l"] > low_min) & base["valid"],
            "short_base": (base["cvd"] > cvd_max) & (base["h"] < high_max) & base["valid"],
            "mag_long": mag_l, "mag_short": mag_s,
        }
    return out


def make_signal_mask(base: dict[str, Any], pre: dict[int, dict[str, np.ndarray]],
                     params: dict[str, float | int]) -> np.ndarray:
    p = pre[int(params["cvd_lookback"])]
    atr_gate = base["atr"] >= float(params["atr_mult"]) * base["atr_ref"]
    vol_gate = base["v"] >= float(params["vol_mult"]) * base["vol_ref"]
    long_mask = (
        p["long_base"] & (p["mag_long"] >= float(params["mag_mult"]))
        & (base["dist_val_atr"] <= float(params["loc_tol_atr"])) & atr_gate & vol_gate
    )
    short_mask = (
        p["short_base"] & (p["mag_short"] >= float(params["mag_mult"]))
        & (base["dist_vah_atr"] <= float(params["loc_tol_atr"])) & atr_gate & vol_gate
    )
    sig = np.zeros(len(base["c"]), dtype=np.int8)
    sig[long_mask], sig[short_mask] = 1, -1
    sig[long_mask & short_mask] = 0
    return sig


def _price_model_trade(base: dict[str, Any], i: int, entry_i: int, side: int,
                       cfg: Config, hi: int) -> dict[str, Any] | None:
    o, h, l, c, atr = (base[k] for k in ("o", "h", "l", "c", "atr"))
    if not math.isfinite(float(atr[i])) or atr[i] <= 0:
        return None
    slip = cfg.slippage_ticks * cfg.tick_size
    entry = float(o[entry_i] + side*slip)
    anchor = float(l[i] if side == 1 else h[i])
    stop = anchor - side*cfg.stop_buffer_atr*float(atr[i])
    if (side == 1 and entry <= stop) or (side == -1 and entry >= stop):
        return None
    risk_price = abs(entry-stop)
    if risk_price <= 0 or not math.isfinite(risk_price):
        return None
    target = entry + side*cfg.rr*risk_price
    last = min(entry_i+cfg.max_hold-1, hi-1)
    reason, exit_price, exit_i = "", 0.0, last
    resolved = False
    for j in range(entry_i, last+1):
        stop_hit = bool(l[j] <= stop) if side == 1 else bool(h[j] >= stop)
        target_hit = bool(h[j] >= target) if side == 1 else bool(l[j] <= target)
        if stop_hit:  # worst-case if stop and target both occur in one OHLC bar
            exit_price, reason, exit_i, resolved = stop-side*slip, "stop", j, True
            break
        if target_hit:
            exit_price, reason, exit_i, resolved = target, "target", j, True
            break
    if not resolved:
        if last >= hi-1:
            return None
        exit_price, reason, exit_i = float(c[last]-side*slip), "time", last
    return {
        "entry_i": entry_i, "exit_i": exit_i, "side": side, "entry": entry,
        "stop": float(stop), "target": float(target), "exit_price": float(exit_price),
        "reason": reason, "bars_held": exit_i-entry_i+1, "risk_price": float(risk_price),
    }


def simulate(base: dict[str, Any], signals: np.ndarray, cfg: Config,
             lo: int, hi: int) -> list[dict[str, Any]]:
    """One non-overlapping position at a time; signals execute on the next bar."""
    if not 0 <= lo < hi <= len(signals):
        raise ValueError("invalid simulation bounds")
    candidates = np.flatnonzero(signals != 0)
    candidates = candidates[(candidates >= lo) & (candidates < hi-1)]
    trades: list[dict[str, Any]] = []
    busy_until = lo-1
    spread = cfg.spread_ticks*cfg.tick_size
    for i_raw in candidates:
        i = int(i_raw)
        entry_i = i+1
        if entry_i <= busy_until or entry_i >= hi:
            continue
        side = int(signals[i])
        if cfg.contract_type == "RISE_FALL_PROXY":
            exit_i = entry_i+cfg.rf_duration_bars
            if exit_i >= hi:
                continue
            entry, exit_price = float(base["o"][entry_i]), float(base["c"][exit_i])
            win = side*(exit_price-entry) > 0.0  # ties are losses (conservative)
            pnl = cfg.stake*cfg.payout_pct if win else -cfg.stake
            trades.append({
                "entry_time": base["index"][entry_i].isoformat(),
                "exit_time": base["index"][exit_i].isoformat(),
                "side": side, "entry": entry, "exit_price": exit_price,
                "reason": "fixed_expiry", "bars_held": cfg.rf_duration_bars,
                "pnl_cash_proxy": pnl, "R": pnl/cfg.stake,
                "model": "binary payout screen; payout_pct must match observed proposal economics",
            })
            busy_until = exit_i
            continue
        model = _price_model_trade(base, i, entry_i, side, cfg, hi)
        if model is None:
            continue
        entry, exit_price = model["entry"], model["exit_price"]
        if cfg.contract_type == "MULTIPLIER_PROXY":
            gross = cfg.stake*side*((exit_price-entry)/max(abs(entry), 1e-12))*cfg.multiplier
            pnl = max(-cfg.stake, gross-cfg.multiplier_commission_cash)
            risk_unit = cfg.stake
            model_name = "stake-capped multiplier formula approximation; commission and fills unverified"
        elif cfg.contract_type == "CFD_PROXY":
            risk_budget = cfg.equity*cfg.risk_fraction
            denominator = (
                model["risk_price"] + spread + cfg.slippage_ticks*cfg.tick_size
                + (cfg.commission_bps/10_000.0)*abs(entry)
            )
            if denominator <= 0:
                continue
            size = risk_budget/denominator
            commission = (cfg.commission_bps/10_000.0)*abs(entry*size)
            pnl = side*(exit_price-entry)*size - spread*size - commission
            risk_unit = risk_budget
            model_name = "linear CFD-like price P&L with assumed friction inputs"
        else:
            raise ValueError(f"unsupported contract_type: {cfg.contract_type}")
        trades.append({
            "entry_time": base["index"][model["entry_i"]].isoformat(),
            "exit_time": base["index"][model["exit_i"]].isoformat(),
            "side": side, "entry": entry, "stop": model["stop"], "target": model["target"],
            "exit_price": exit_price, "reason": model["reason"], "bars_held": model["bars_held"],
            "pnl_cash_proxy": float(pnl), "R": float(pnl/risk_unit),
            "model": model_name,
        })
        busy_until = int(model["exit_i"])
    return trades


def calculate_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"trades": 0, "win_rate": None, "profit_factor": None,
                "expectancy_R": 0.0, "net_R": 0.0, "max_drawdown_R": 0.0,
                "avg_win_R": None, "avg_loss_R": None}
    ordered = sorted(trades, key=lambda t: (t["entry_time"], t["exit_time"]))
    r = np.asarray([float(t["R"]) for t in ordered], dtype=float)
    if not np.isfinite(r).all():
        raise ValueError("non-finite R-multiple detected")
    wins, losses = r[r > 0], r[r <= 0]
    gp = float(wins.sum()) if len(wins) else 0.0
    gl = float(-losses.sum()) if len(losses) else 0.0
    equity = np.cumsum(r)
    peak = np.maximum.accumulate(np.concatenate(([0.0], equity)))[1:]
    pf = gp/gl if gl > 0 else None
    return {
        "trades": len(r), "win_rate": round(float((r > 0).mean()), 4),
        "profit_factor": round(float(pf), 4) if pf is not None else None,
        "expectancy_R": round(float(r.mean()), 5), "net_R": round(float(r.sum()), 4),
        "max_drawdown_R": round(float(np.max(peak-equity)), 4),
        "avg_win_R": round(float(wins.mean()), 4) if len(wins) else None,
        "avg_loss_R": round(float(losses.mean()), 4) if len(losses) else None,
    }


def all_param_combinations() -> list[dict[str, float | int]]:
    keys = list(SIGNAL_GRID)
    return [dict(zip(keys, values)) for values in itertools.product(*(SIGNAL_GRID[k] for k in keys))]


def walk_forward(base: dict[str, Any], pre: dict[int, dict[str, np.ndarray]], cfg: Config):
    n = len(base["c"])
    warmup = max(cfg.vp_lookback, cfg.atr_period+cfg.atr_ref, cfg.vol_ref, 20)+5
    if n < warmup+cfg.is_bars+cfg.oos_bars:
        raise ValueError(f"insufficient data: need >= {warmup+cfg.is_bars+cfg.oos_bars} valid bars, found {n}")
    combos = all_param_combinations()
    cursor = warmup
    folds: list[dict[str, Any]] = []
    pooled: list[dict[str, Any]] = []
    selections: Counter[str] = Counter()
    while cursor+cfg.is_bars+cfg.oos_bars <= n:
        is_lo, is_hi = cursor, cursor+cfg.is_bars
        oos_lo, oos_hi = is_hi, is_hi+cfg.oos_bars
        best = None
        for params in combos:
            sig = make_signal_mask(base, pre, params)
            m = calculate_metrics(simulate(base, sig, cfg, is_lo, is_hi))
            pf = m["profit_factor"]
            if m["trades"] < cfg.min_is_trades or pf is None or pf < 1.0:
                continue
            if best is None or m["expectancy_R"] > best[0]:
                best = (m["expectancy_R"], params, m)
        if best is None:
            folds.append({
                "oos_start": base["index"][oos_lo].isoformat(),
                "oos_end": base["index"][oos_hi-1].isoformat(),
                "status": "no_eligible_in_sample_parameters", "oos_trades": 0,
                "oos_expectancy_R": 0.0, "oos_profit_factor": None, "params": None,
            })
            cursor += cfg.oos_bars
            continue
        _, params, is_metrics = best
        key = json.dumps(params, sort_keys=True)
        selections[key] += 1
        oos_trades = simulate(base, make_signal_mask(base, pre, params), cfg, oos_lo, oos_hi)
        oos_metrics = calculate_metrics(oos_trades)
        folds.append({
            "oos_start": base["index"][oos_lo].isoformat(),
            "oos_end": base["index"][oos_hi-1].isoformat(), "status": "evaluated",
            "params": key, "is_trades": is_metrics["trades"],
            "is_expectancy_R": is_metrics["expectancy_R"],
            **{f"oos_{k}": v for k, v in oos_metrics.items()},
        })
        pooled.extend(oos_trades)
        cursor += cfg.oos_bars
    pooled_metrics = calculate_metrics(pooled)
    # Empty/no-eligible folds count as non-positive, preventing denominator shrinkage.
    assessed = [f for f in folds if f.get("status") in ("evaluated", "no_eligible_in_sample_parameters")]
    positive_share = (
        sum(float(f.get("oos_expectancy_R", 0.0)) > 0 for f in assessed)/len(assessed)
        if assessed else 0.0
    )
    return folds, pooled, pooled_metrics, positive_share, dict(selections)


def governance_verdict(metrics: dict[str, Any], positive_share: float, cfg: Config) -> dict[str, Any]:
    pf = metrics["profit_factor"]
    gates = {
        "min_oos_trades": metrics["trades"] >= cfg.min_oos_trades,
        "profit_factor_threshold": pf is not None and pf >= cfg.min_profit_factor,
        "expectancy_threshold": metrics["expectancy_R"] >= cfg.min_expectancy_r,
        "max_drawdown_threshold": metrics["max_drawdown_R"] <= cfg.max_drawdown_r,
        "positive_fold_share_threshold": positive_share >= cfg.min_positive_fold_share,
    }
    return {
        "gates": gates,
        "decision": "PASS_FOR_FORWARD_PAPER_ONLY" if all(gates.values()) else "FAIL_DO_NOT_DEPLOY_CAPITAL",
        "authority": "RESEARCH_ONLY_NO_CAPITAL_AUTHORITY",
    }


def run_one(df: pd.DataFrame, coverage: dict[str, Any], cfg: Config, out_dir: Path,
            base: dict[str, Any], pre: dict[int, dict[str, np.ndarray]]) -> dict[str, Any]:
    cfg.validate()
    out_dir.mkdir(parents=True, exist_ok=True)
    folds, trades, pooled_metrics, positive_share, selections = walk_forward(base, pre, cfg)
    pd.DataFrame(folds).to_csv(out_dir/"folds.csv", index=False)
    pd.DataFrame(trades).to_csv(out_dir/"oos_trades.csv", index=False)
    summary = {
        "schema": "aurelia.deriv_tick_momentum_absorption_research.v1",
        "research_only": True, "capital_authority": False, "live_execution": False,
        "contract_type": cfg.contract_type, "coverage": coverage, "configuration": asdict(cfg),
        "signal_grid_size": len(all_param_combinations()), "walk_forward_folds": len(folds),
        "positive_oos_fold_share": round(float(positive_share), 5),
        "pooled_out_of_sample": pooled_metrics, "parameter_selection_frequency": selections,
        "decision": governance_verdict(pooled_metrics, positive_share, cfg),
        "assumptions_and_limits": [
            "CVD is close-direction times supplied volume; not bid/ask aggressor delta.",
            "OHLCV volume-at-price is a uniform-range proxy, not an exchange-grade volume profile.",
            "Entry is next bar open with adverse assumed slippage; signal uses closed bars only.",
            "Stop wins if stop and target are both inside the same OHLC bar.",
            "Trades unresolved at a fold boundary are excluded.",
            "CFD and multiplier cash results are approximations requiring observed costs and fills.",
            "Rise/Fall uses fixed-expiry payout, not structural SL/TP; ties are losses.",
            "PASS means forward paper validation only and never authorizes live trading.",
        ],
    }
    (out_dir/"summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"contract_type": cfg.contract_type, "metrics": pooled_metrics,
                      "decision": summary["decision"]}, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--out", default="wf_deriv_absorption")
    parser.add_argument("--contract-type", choices=["CFD_PROXY", "MULTIPLIER_PROXY", "RISE_FALL_PROXY", "all"], default="all")
    parser.add_argument("--tick-size", type=float, default=0.01, help="Placeholder; verify from symbol specification")
    parser.add_argument("--is-bars", type=int, default=20_000)
    parser.add_argument("--oos-bars", type=int, default=5_000)
    parser.add_argument("--multiplier", type=float, default=10.0, help="Fixed scenario, not optimizer-selected")
    parser.add_argument("--stake", type=float, default=1.0)
    parser.add_argument("--equity", type=float, default=1000.0)
    parser.add_argument("--risk-fraction", type=float, default=0.005)
    parser.add_argument("--payout-pct", type=float, default=0.90, help="Assumption; replace with observed proposal payout")
    parser.add_argument("--rf-duration-bars", type=int, default=5)
    parser.add_argument("--spread-ticks", type=float, default=1.0)
    parser.add_argument("--slippage-ticks", type=float, default=0.5)
    parser.add_argument("--commission-bps", type=float, default=0.0)
    parser.add_argument("--multiplier-commission-cash", type=float, default=0.0)
    args = parser.parse_args()
    df, coverage = load_data(args.csv)
    print("DATA VALIDATION:")
    print(json.dumps(coverage, indent=2))
    base_cfg = Config(
        tick_size=args.tick_size, is_bars=args.is_bars, oos_bars=args.oos_bars,
        multiplier=args.multiplier, stake=args.stake, equity=args.equity,
        risk_fraction=args.risk_fraction, payout_pct=args.payout_pct,
        rf_duration_bars=args.rf_duration_bars, spread_ticks=args.spread_ticks,
        slippage_ticks=args.slippage_ticks, commission_bps=args.commission_bps,
        multiplier_commission_cash=args.multiplier_commission_cash,
    )
    choices: list[ContractType] = (
        ["CFD_PROXY", "MULTIPLIER_PROXY", "RISE_FALL_PROXY"]
        if args.contract_type == "all" else [args.contract_type]  # type: ignore[list-item]
    )
    root = Path(args.out)
    print(f"Building common features once for {len(df)} bars...")
    vah, val = build_profile(df, base_cfg)
    base = build_base(df, base_cfg, vah, val)
    pre = precompute_divergences(base)
    summaries = {}
    for choice in choices:
        cfg = replace(base_cfg, contract_type=choice)
        summaries[choice] = run_one(df, coverage, cfg, root/choice.lower(), base, pre)
    root.mkdir(parents=True, exist_ok=True)
    (root/"comparison.json").write_text(json.dumps({
        "research_only": True, "live_execution": False, "runs": summaries,
    }, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Reports written to {root.resolve()}")


if __name__ == "__main__":
    main()
