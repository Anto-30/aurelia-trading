"""Phase 6 / Phase 6+Layer 9 time-filter research harness.

Research-only: this module computes signals and simulates historical trades. It has
no broker, capital, or order-submission interface. Bars must be timestamped by bar
OPEN time and carry timezone-aware timestamps. Signal conditions are evaluated only
on the closed 08:50 New York bar; entry is the next minute's open (08:51).

For a 15-minute holding interval with bar-open timestamps, the time exit is the
CLOSE of the bar timestamped 09:05 (actual bar close at 09:06). This convention is
explicit to avoid accidentally entering/exiting on a candle before its close.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from dataclasses import asdict, dataclass
from datetime import time, timedelta
from pathlib import Path
from typing import Any, Literal

import pandas as pd

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
ORDER_SUBMISSION_PERMITTED = False
TIMEZONE_NAME = "America/New_York"

Variant = Literal["PHASE6_ONLY", "PHASE6_PLUS_9"]


@dataclass(frozen=True)
class BacktestConfig:
    """Frozen rule and execution assumptions for a single research run.

    Costs are mandatory for a backtest. Pass explicit zeroes only when intentionally
    running a zero-cost sensitivity; zero is not presented as a real-market estimate.
    """

    target_time_rounded: str = "08:50:00"
    exit_time_rounded: str = "09:05:00"
    timezone: str = TIMEZONE_NAME
    timestamp_semantics: str = "BAR_OPEN"
    ema_fast_period: int = 20
    ema_slow_period: int = 200
    volume_window: int = 20
    volume_multiplier: float = 1.5
    atr_period: int = 14
    phase6_stop_tr_multiple: float = 1.0
    phase6_plus_9_stop_atr_multiple: float = 1.5
    commission_per_share_per_side: float | None = None
    slippage_per_share_per_side: float | None = None

    def __post_init__(self) -> None:
        try:
            target = time.fromisoformat(self.target_time_rounded)
            exit_time = time.fromisoformat(self.exit_time_rounded)
        except (TypeError, ValueError) as exc:
            raise ValueError("TARGET_OR_EXIT_TIME_INVALID") from exc
        if target.second or target.microsecond or exit_time.second or exit_time.microsecond:
            raise ValueError("TARGET_AND_EXIT_TIMES_MUST_BE_MINUTE_ALIGNED")
        if target >= exit_time:
            raise ValueError("EXIT_TIME_MUST_FOLLOW_TARGET_TIME")
        if self.timestamp_semantics != "BAR_OPEN":
            raise ValueError("ONLY_BAR_OPEN_TIMESTAMP_SEMANTICS_SUPPORTED")
        if min(self.ema_fast_period, self.ema_slow_period, self.volume_window, self.atr_period) < 1:
            raise ValueError("INDICATOR_PERIODS_MUST_BE_POSITIVE")
        if self.ema_fast_period >= self.ema_slow_period:
            raise ValueError("FAST_EMA_PERIOD_MUST_BE_LESS_THAN_SLOW_EMA_PERIOD")
        for name in ("volume_multiplier", "phase6_stop_tr_multiple", "phase6_plus_9_stop_atr_multiple"):
            value = getattr(self, name)
            if not math.isfinite(float(value)) or value <= 0:
                raise ValueError(f"{name.upper()}_MUST_BE_FINITE_AND_POSITIVE")
        for name in ("commission_per_share_per_side", "slippage_per_share_per_side"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(float(value)) or value < 0):
                raise ValueError(f"{name.upper()}_MUST_BE_FINITE_AND_NONNEGATIVE")


def _time(value: str) -> time:
    return time.fromisoformat(value)


def _prepare_frame(df: pd.DataFrame, config: BacktestConfig, *, require_volume: bool) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("OHLC_INPUT_MUST_BE_PANDAS_DATAFRAME")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("INDEX_MUST_BE_DATETIMEINDEX_OR_LOADER_MUST_SET_TIMESTAMP_INDEX")
    if df.index.tz is None:
        raise ValueError("BAR_TIMESTAMPS_MUST_BE_TIMEZONE_AWARE")
    if not df.index.is_monotonic_increasing:
        raise ValueError("BAR_TIMESTAMPS_MUST_BE_STRICTLY_INCREASING")
    if df.index.has_duplicates:
        raise ValueError("BAR_TIMESTAMPS_MUST_BE_UNIQUE")
    local_index = df.index.tz_convert(config.timezone)
    if any((stamp.second != 0 or stamp.microsecond != 0) for stamp in local_index):
        raise ValueError("BAR_TIMESTAMPS_MUST_BE_MINUTE_ALIGNED")

    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError("OHLC_COLUMNS_MISSING:" + ",".join(sorted(missing)))
    if require_volume and "volume" not in df.columns:
        raise ValueError("VOLUME_COLUMN_REQUIRED_FOR_PHASE6_PLUS_9")

    out = df.copy(deep=True)
    out.index = local_index
    numeric = list(required) + (["volume"] if "volume" in out.columns else [])
    for col in numeric:
        out[col] = pd.to_numeric(out[col], errors="coerce")
        if out[col].isna().any() or not out[col].map(lambda x: math.isfinite(float(x))).all():
            raise ValueError(f"{col.upper()}_CONTAINS_MISSING_OR_NONFINITE_VALUES")
    for col in ("open", "high", "low", "close"):
        if (out[col] <= 0).any():
            raise ValueError("OHLC_PRICES_MUST_BE_POSITIVE")
    if ((out.high < out[["open", "close", "low"]].max(axis=1)) |
            (out.low > out[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("OHLC_BAR_INCONSISTENT")
    if "volume" in out.columns and (out.volume < 0).any():
        raise ValueError("VOLUME_MUST_BE_NONNEGATIVE")
    return out


def _wilder_atr(frame: pd.DataFrame, period: int) -> pd.Series:
    """Wilder ATR with an SMA seed, using only current and prior bars."""
    prev_close = frame.close.shift(1)
    tr = pd.concat(
        [frame.high - frame.low, (frame.high - prev_close).abs(), (frame.low - prev_close).abs()],
        axis=1,
    ).max(axis=1, skipna=True)
    values = tr.to_list()
    atr = [math.nan] * len(values)
    if len(values) >= period:
        seed = sum(float(x) for x in values[:period]) / period
        atr[period - 1] = seed
        for i in range(period, len(values)):
            atr[i] = ((period - 1) * atr[i - 1] + float(values[i])) / period
    return pd.Series(atr, index=frame.index, name=f"atr_{period}", dtype="float64")


def _features(df: pd.DataFrame, config: BacktestConfig, *, require_volume: bool) -> pd.DataFrame:
    frame = _prepare_frame(df, config, require_volume=require_volume)
    frame["ema_20"] = frame.close.ewm(
        span=config.ema_fast_period, adjust=False, min_periods=config.ema_fast_period
    ).mean()
    frame["ema_200"] = frame.close.ewm(
        span=config.ema_slow_period, adjust=False, min_periods=config.ema_slow_period
    ).mean()
    frame["true_range"] = pd.concat(
        [frame.high - frame.low,
         (frame.high - frame.close.shift(1)).abs(),
         (frame.low - frame.close.shift(1)).abs()], axis=1,
    ).max(axis=1, skipna=True)
    frame[f"atr_{config.atr_period}"] = _wilder_atr(frame, config.atr_period)
    # Excludes the signal bar's volume from its reference baseline. This avoids
    # diluting the required volume spike with the very observation being tested.
    if "volume" in frame.columns:
        frame["prior_volume_ma"] = frame.volume.shift(1).rolling(
            config.volume_window, min_periods=config.volume_window
        ).mean()
    frame["atr_expanding"] = frame[f"atr_{config.atr_period}"] > frame[f"atr_{config.atr_period}"].shift(1)
    return frame


def _target_mask(index: pd.DatetimeIndex, target_time: str) -> pd.Series:
    target = _time(target_time)
    return pd.Series(
        (index.hour == target.hour) & (index.minute == target.minute),
        index=index,
        dtype=bool,
    )


def generate_phase6_signals(df: pd.DataFrame, config: BacktestConfig = BacktestConfig()) -> pd.Series:
    """Return +1/-1/0 on the closed signal bar; fill is not assumed on that bar."""
    frame = _features(df, config, require_volume=False)
    is_target_time = _target_mask(frame.index, config.target_time_rounded)
    long_condition = is_target_time & (frame.close > frame.open) & (frame.close > frame.ema_20)
    short_condition = is_target_time & (frame.close < frame.open) & (frame.close < frame.ema_20)
    signals = pd.Series(0, index=frame.index, dtype="int8", name="phase6_signal")
    signals.loc[long_condition.fillna(False)] = 1
    signals.loc[short_condition.fillna(False)] = -1
    return signals


def generate_phase6_plus_9_signals(
    df: pd.DataFrame, config: BacktestConfig = BacktestConfig()
) -> pd.Series:
    """Phase 6 signal gated by Layer 9 volume, EMA200, and ATR-expansion filters."""
    frame = _features(df, config, require_volume=True)
    is_target_time = _target_mask(frame.index, config.target_time_rounded)
    volume_pop = frame.volume > config.volume_multiplier * frame.prior_volume_ma
    long_condition = (
        is_target_time & (frame.close > frame.open) & (frame.close > frame.ema_20)
        & (frame.close > frame.ema_200) & volume_pop & frame.atr_expanding
    )
    short_condition = (
        is_target_time & (frame.close < frame.open) & (frame.close < frame.ema_20)
        & (frame.close < frame.ema_200) & volume_pop & frame.atr_expanding
    )
    signals = pd.Series(0, index=frame.index, dtype="int8", name="phase6_plus_9_signal")
    signals.loc[long_condition.fillna(False)] = 1
    signals.loc[short_condition.fillna(False)] = -1
    return signals


TRADE_COLUMNS = [
    "model", "signal_timestamp_ny", "entry_timestamp_ny", "entry_timestamp_utc",
    "side", "entry_raw_price", "stop_price", "exit_bar_timestamp_ny",
    "exit_execution_timestamp_ny", "exit_time_precision", "exit_raw_price", "exit_reason", "stop_distance",
    "gross_pnl_per_share_before_costs", "slippage_cost_per_share", "commission_cost_per_share",
    "net_pnl_per_share", "net_r_multiple", "holding_minutes", "evidence_codes",
]


def _costs(config: BacktestConfig) -> tuple[float, float]:
    if config.commission_per_share_per_side is None or config.slippage_per_share_per_side is None:
        raise ValueError("EXPLICIT_COMMISSION_AND_SLIPPAGE_REQUIRED; zero-cost tests must pass explicit 0.0")
    return float(config.commission_per_share_per_side), float(config.slippage_per_share_per_side)


def _trade_metrics(trades: pd.DataFrame) -> dict[str, Any]:
    n = len(trades)
    if n == 0:
        return {
            "trade_count": 0, "win_rate": None, "gross_pnl_per_share": 0.0,
            "net_pnl_per_share": 0.0, "expectancy_net_per_share": None,
            "expectancy_net_r": None, "profit_factor_net": None,
            "profit_factor_status": "NO_CLOSED_TRADES", "max_drawdown_r": None,
            "average_holding_minutes": None,
        }
    pnl = trades.net_pnl_per_share.astype(float)
    r_values = trades.net_r_multiple.astype(float)
    winners = float(pnl[pnl > 0].sum())
    losers = float(pnl[pnl < 0].sum())
    if losers < 0:
        pf: float | None = winners / abs(losers)
        pf_status = "DEFINED"
    else:
        pf = None
        pf_status = "NO_LOSSES_DENOMINATOR_ZERO"
    equity = r_values.cumsum()
    high_water = equity.cummax().clip(lower=0.0)
    drawdown = high_water - equity
    return {
        "trade_count": n,
        "win_rate": float((pnl > 0).mean()),
        "gross_pnl_per_share": float(trades.gross_pnl_per_share_before_costs.sum()),
        "net_pnl_per_share": float(pnl.sum()),
        "expectancy_net_per_share": float(pnl.mean()),
        "expectancy_net_r": float(r_values.mean()),
        "profit_factor_net": pf,
        "profit_factor_status": pf_status,
        "max_drawdown_r": float(drawdown.max()),
        "average_holding_minutes": float(trades.holding_minutes.mean()),
    }


def run_phase6_backtest(
    df: pd.DataFrame,
    *,
    variant: Variant,
    config: BacktestConfig,
) -> dict[str, Any]:
    """Run one research-only model, with next-bar entry and pessimistic stop handling."""
    commission, slippage = _costs(config)
    if variant not in ("PHASE6_ONLY", "PHASE6_PLUS_9"):
        raise ValueError("VARIANT_UNSUPPORTED")
    frame = _features(df, config, require_volume=(variant == "PHASE6_PLUS_9"))
    signals = generate_phase6_signals(df, config) if variant == "PHASE6_ONLY" else generate_phase6_plus_9_signals(df, config)
    exit_time = _time(config.exit_time_rounded)
    stop_multiple = config.phase6_stop_tr_multiple if variant == "PHASE6_ONLY" else config.phase6_plus_9_stop_atr_multiple
    trades: list[dict[str, Any]] = []
    skip_counts: dict[str, int] = {}
    last_traded_date: str | None = None

    def skip(reason: str) -> None:
        skip_counts[reason] = skip_counts.get(reason, 0) + 1

    for i, raw_signal in enumerate(signals.to_list()):
        side = int(raw_signal)
        if side == 0:
            continue
        signal_ts = frame.index[i]
        signal_date = signal_ts.date().isoformat()
        if signal_ts.time() != _time(config.target_time_rounded):
            skip("SIGNAL_OUTSIDE_TARGET_TIME")
            continue
        if last_traded_date == signal_date:
            skip("ONE_TRADE_PER_LOCAL_DATE_LIMIT")
            continue
        # Use the close-confirmed signal bar only to set direction/stop reference;
        # actual simulated entry is the following minute's open.
        entry_ts = signal_ts + timedelta(minutes=1)
        entry_i = i + 1
        if entry_i >= len(frame) or frame.index[entry_i] != entry_ts:
            skip("NEXT_MINUTE_ENTRY_BAR_MISSING")
            continue
        entry_row = frame.iloc[entry_i]
        signal_row = frame.iloc[i]
        if variant == "PHASE6_ONLY":
            stop_distance = float(signal_row.true_range) * stop_multiple
            stop_reference = "SIGNAL_BAR_TRUE_RANGE"
        else:
            atr_value = signal_row[f"atr_{config.atr_period}"]
            if pd.isna(atr_value) or float(atr_value) <= 0:
                skip("ATR_UNAVAILABLE_FOR_STOP")
                continue
            stop_distance = float(atr_value) * stop_multiple
            stop_reference = "SIGNAL_BAR_WILDER_ATR"
        if not math.isfinite(stop_distance) or stop_distance <= 0:
            skip("STOP_DISTANCE_INVALID")
            continue
        # Bar-open convention: exit on the close of the 09:05 bar. Its actual
        # execution timestamp is 09:06, exactly 15 minutes after the 08:51 entry.
        exit_wall = signal_ts.replace(hour=exit_time.hour, minute=exit_time.minute, second=0, microsecond=0)
        try:
            exit_i = frame.index.get_loc(exit_wall)
        except KeyError:
            skip("SCHEDULED_EXIT_BAR_MISSING")
            continue
        if not isinstance(exit_i, int) or exit_i < entry_i:
            skip("SCHEDULED_EXIT_BAR_INVALID")
            continue
        expected = pd.date_range(entry_ts, exit_wall, freq="min")
        if not expected.isin(frame.index).all():
            skip("MISSING_MINUTE_BAR_DURING_HOLD")
            continue

        entry_raw = float(entry_row.open)
        stop_price = entry_raw - side * stop_distance
        exit_raw: float | None = None
        exit_reason: str | None = None
        exit_bar_ts = None
        exit_exec_ts = None
        exit_time_precision = "UNKNOWN_UNTIL_EXIT_CLASSIFIED"
        for k in range(entry_i, exit_i + 1):
            row = frame.iloc[k]
            hit = float(row.low) <= stop_price if side == 1 else float(row.high) >= stop_price
            if hit:
                # Stop-first, adverse-gap model: if the bar opens beyond the stop,
                # assume the open; otherwise assume the stop price. Then charge slip.
                if side == 1:
                    exit_raw = min(float(row.open), stop_price)
                else:
                    exit_raw = max(float(row.open), stop_price)
                exit_reason = "HARD_STOP"
                exit_bar_ts = frame.index[k]
                # OHLC bars only identify the bar containing a stop touch; exact
                # intrabar execution time is unknowable without tick/order data.
                exit_exec_ts = None
                exit_time_precision = "INTRABAR_TIME_UNKNOWN_OHLC_ONLY"
                break
        if exit_raw is None:
            final_row = frame.iloc[exit_i]
            exit_raw = float(final_row.close)
            exit_reason = "TIME_EXIT_09_05_BAR_CLOSE"
            exit_bar_ts = frame.index[exit_i]
            exit_exec_ts = frame.index[exit_i] + timedelta(minutes=1)
            exit_time_precision = "BAR_CLOSE_TIME_FROM_BAR_OPEN_LABEL"

        gross = side * (exit_raw - entry_raw)
        slip_cost = 2.0 * slippage
        commission_cost = 2.0 * commission
        net = gross - slip_cost - commission_cost
        trades.append({
            "model": variant,
            "signal_timestamp_ny": signal_ts.isoformat(),
            "entry_timestamp_ny": entry_ts.isoformat(),
            "entry_timestamp_utc": entry_ts.tz_convert("UTC").isoformat(),
            "side": "LONG" if side == 1 else "SHORT",
            "entry_raw_price": entry_raw,
            "stop_price": stop_price,
            "exit_bar_timestamp_ny": exit_bar_ts.isoformat(),
            "exit_execution_timestamp_ny": exit_exec_ts.isoformat() if exit_exec_ts is not None else None,
            "exit_time_precision": exit_time_precision,
            "exit_raw_price": exit_raw,
            "exit_reason": exit_reason,
            "stop_distance": stop_distance,
            "stop_reference": stop_reference,
            "gross_pnl_per_share_before_costs": gross,
            "slippage_cost_per_share": slip_cost,
            "commission_cost_per_share": commission_cost,
            "net_pnl_per_share": net,
            "net_r_multiple": net / stop_distance,
            "holding_minutes": (exit_exec_ts - entry_ts).total_seconds() / 60.0 if exit_exec_ts is not None else None,
            "evidence_codes": "TARGET_TIME|CLOSED_BAR_SIGNAL|NEXT_BAR_OPEN_FILL|STOP_FIRST|EXPLICIT_COSTS",
        })
        last_traded_date = signal_date

    trade_df = pd.DataFrame(trades)
    if trade_df.empty:
        trade_df = pd.DataFrame(columns=TRADE_COLUMNS + ["stop_reference"])
    metrics = _trade_metrics(trade_df)
    return {
        "model": variant,
        "status": "RESEARCH_ONLY_UNQUALIFIED",
        "research_only": True,
        "capital_authority": False,
        "live_execution": False,
        "order_submission_permitted": False,
        "config": asdict(config),
        "costs": {
            "commission_per_share_per_side": commission,
            "slippage_per_share_per_side": slippage,
            "status": "USER_SUPPLIED_ASSUMPTION_NOT_VERIFIED_EXECUTION_COST",
        },
        "signal_count": int((signals != 0).sum()),
        "trades": trade_df,
        "metrics": metrics,
        "skipped_signals": skip_counts,
    }


def _load_parquet(path: Path, timestamp_column: str, source_timezone: str | None) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    if timestamp_column in frame.columns:
        raw_timestamps = frame.pop(timestamp_column)
        parsed = [pd.Timestamp(value) for value in raw_timestamps]
        awareness = [stamp.tzinfo is not None for stamp in parsed]
        if any(awareness) and not all(awareness):
            raise ValueError("TIMESTAMP_COLUMN_MIXES_AWARE_AND_NAIVE_VALUES")
        if all(awareness) and parsed:
            # Normalize mixed fixed offsets to UTC before New York conversion; this
            # preserves chronology when the file spans a daylight-saving change.
            frame.index = pd.DatetimeIndex(pd.to_datetime(parsed, utc=True))
        else:
            if not source_timezone:
                raise ValueError("NAIVE_TIMESTAMP_COLUMN_REQUIRES_EXPLICIT_SOURCE_TIMEZONE")
            naive_index = pd.DatetimeIndex(pd.to_datetime(parsed, errors="raise"))
            frame.index = naive_index.tz_localize(source_timezone, ambiguous="raise", nonexistent="raise")
    elif not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("PARQUET_NEEDS_DATETIME_INDEX_OR_TIMESTAMP_COLUMN")
    if frame.index.tz is None:
        if not source_timezone:
            raise ValueError("NAIVE_TIMESTAMP_INDEX_REQUIRES_EXPLICIT_SOURCE_TIMEZONE")
        frame.index = frame.index.tz_localize(source_timezone, ambiguous="raise", nonexistent="raise")
    return frame.sort_index()


def _safe_git_sha() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=3
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path, help="Input 1-minute OHLCV Parquet")
    parser.add_argument("--timestamp-column", default="timestamp", help="Timestamp column; ignored if datetime index exists")
    parser.add_argument("--source-timezone", default=None, help="Required to interpret naive timestamps; e.g. UTC")
    parser.add_argument("--target-time", default="08:50:00")
    parser.add_argument("--exit-time", default="09:05:00")
    parser.add_argument("--commission-per-share-per-side", required=True, type=float,
                        help="Explicit commission assumption; pass 0 only for an intentional zero-cost sensitivity")
    parser.add_argument("--slippage-per-share-per-side", required=True, type=float,
                        help="Explicit one-way adverse slippage assumption; pass 0 only for sensitivity analysis")
    parser.add_argument("--oos-start", default=None, help="Optional ISO timestamp/date for untouched out-of-sample reporting")
    parser.add_argument("--variants", nargs="+", choices=("PHASE6_ONLY", "PHASE6_PLUS_9"),
                        default=["PHASE6_ONLY", "PHASE6_PLUS_9"],
                        help="Variants to run; omit to run both (requires volume for PHASE6_PLUS_9)")
    parser.add_argument("--outdir", type=Path, default=Path("artifacts/phase6_research"))
    args = parser.parse_args(argv)
    if not args.data.is_file():
        parser.error(f"DATA_FILE_NOT_FOUND: {args.data}")
    try:
        frame = _load_parquet(args.data, args.timestamp_column, args.source_timezone)
        config = BacktestConfig(
            target_time_rounded=args.target_time, exit_time_rounded=args.exit_time,
            commission_per_share_per_side=args.commission_per_share_per_side,
            slippage_per_share_per_side=args.slippage_per_share_per_side,
        )
        args.outdir.mkdir(parents=True, exist_ok=True)
        all_report: dict[str, Any] = {
            "schema": "aurelia.phase6_research_report.v1",
            "research_only": True, "capital_authority": False, "live_execution": False,
            "final_execution_authorization": False,
            "data_file_name": args.data.name, "data_sha256": _sha256(args.data),
            "source_revision": _safe_git_sha(), "row_count": len(frame),
            "data_start": frame.index[0].isoformat() if len(frame) else None,
            "data_end": frame.index[-1].isoformat() if len(frame) else None,
            "data_timezone_original": str(frame.index.tz), "config": asdict(config),
            "metrics_are": "BACKTEST_SIMULATION_NOT_BROKER_EVIDENCE",
            "models": {},
        }
        for variant in args.variants:
            result = run_phase6_backtest(frame, variant=variant, config=config)  # type: ignore[arg-type]
            trades: pd.DataFrame = result.pop("trades")
            trades.to_csv(args.outdir / f"{variant.lower()}_trades.csv", index=False)
            result["metrics_scope"] = "FULL_AVAILABLE_SAMPLE"
            if args.oos_start:
                cutoff = pd.Timestamp(args.oos_start)
                if cutoff.tzinfo is None:
                    cutoff = cutoff.tz_localize(config.timezone, ambiguous="raise", nonexistent="raise")
                else:
                    cutoff = cutoff.tz_convert(config.timezone)
                if trades.empty:
                    result["oos_metrics"] = _trade_metrics(trades)
                    result["in_sample_metrics"] = _trade_metrics(trades)
                else:
                    # Compare in UTC so rows spanning DST offset changes remain
                    # parseable as one homogeneous datetime vector.
                    cutoff_utc = cutoff.tz_convert("UTC")
                    entry_times_utc = pd.to_datetime(trades.entry_timestamp_utc, utc=True)
                    oos_mask = entry_times_utc >= cutoff_utc
                    result["oos_metrics"] = _trade_metrics(trades.loc[oos_mask].reset_index(drop=True))
                    result["in_sample_metrics"] = _trade_metrics(trades.loc[~oos_mask].reset_index(drop=True))
                result["oos_start"] = cutoff.isoformat()
            all_report["models"][variant] = result
        report_path = args.outdir / "summary.json"
        report_path.write_text(json.dumps(all_report, indent=2, allow_nan=False), encoding="utf-8")
        print(json.dumps({"report": str(report_path), "data_sha256": all_report["data_sha256"],
                          "row_count": len(frame), "models": {
                              name: {"signal_count": item["signal_count"], "metrics": item["metrics"],
                                     "skipped_signals": item["skipped_signals"]}
                              for name, item in all_report["models"].items()
                          }, "research_only": True, "live_execution": False}, indent=2, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "ABORTED", "reason": type(exc).__name__, "detail": str(exc),
                          "research_only": True, "live_execution": False}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
