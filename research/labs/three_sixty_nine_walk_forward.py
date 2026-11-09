from __future__ import annotations

"""Deterministic historical walk-forward research for 369/MSNR.

This module is research-only and fails closed when source, cost history, swing
provenance, instrument mapping, data continuity, or OOS sample evidence is
missing. It never submits orders or changes execution policy.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from itertools import product
import json
import math
import random
import re
from statistics import mean
from typing import Any, Mapping, Sequence

from research.labs.deterministic_intraday_strategies import StrategyBar, _validate_bars
from research.labs.intraday_bias_cost_model import InstrumentCostProfile
from research.labs.three_sixty_nine_msnr import (
    ProtectedSwing,
    ThreeSixtyNineMSNRConfig,
    bar_close_timestamp,
    evaluate_369_msnr_candidate,
    signal_close_is_eligible,
)
from research.labs.three_sixty_nine_simulator import SimulatedTrade, simulate_candidate


@dataclass(frozen=True)
class WalkForwardConfig:
    training_days: int = 365
    oos_days: int = 90
    step_days: int = 90
    minimum_training_trades: int = 30
    minimum_oos_trades: int = 100
    minimum_net_expectancy_r: float = 0.0
    minimum_profit_factor: float = 1.15
    maximum_drawdown_r: float = 15.0
    bootstrap_replicates: int = 1000
    max_parameter_sets: int = 128
    random_seed: int = 1729

    def __post_init__(self) -> None:
        for name in (
            "training_days", "oos_days", "step_days",
            "minimum_training_trades", "minimum_oos_trades", "bootstrap_replicates",
            "max_parameter_sets",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError("WFO_POLICY_INTEGER_INVALID:" + name)
        if self.step_days < self.oos_days:
            raise ValueError("OOS_WINDOWS_MUST_NOT_OVERLAP")
        for name in ("minimum_net_expectancy_r", "minimum_profit_factor", "maximum_drawdown_r"):
            if not math.isfinite(float(getattr(self, name))):
                raise ValueError("WFO_POLICY_NUMERIC_INVALID:" + name)
        if self.minimum_profit_factor <= 0 or self.maximum_drawdown_r <= 0:
            raise ValueError("WFO_POLICY_LIMIT_INVALID")


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: datetime
    train_end: datetime
    oos_start: datetime
    oos_end: datetime


@dataclass(frozen=True)
class NetRMetrics:
    trade_count: int
    net_expectancy_r: float | None
    profit_factor: float | None
    max_drawdown_r: float | None
    win_rate: float | None


@dataclass(frozen=True)
class ParameterSet:
    lookback_bars: int
    min_sweep_ticks: float
    max_reclaim_bars: int
    displacement_filter: bool
    ema_atr_filter: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "lookback_bars": self.lookback_bars,
            "min_sweep_ticks": self.min_sweep_ticks,
            "max_reclaim_bars": self.max_reclaim_bars,
            "displacement_filter": self.displacement_filter,
            "ema_atr_filter": self.ema_atr_filter,
        }


def _aware_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("WFO_TIMESTAMPS_MUST_BE_AWARE")
    return value.astimezone(timezone.utc)


def build_rolling_windows(
    data_start: datetime,
    data_end: datetime,
    policy: WalkForwardConfig,
) -> tuple[WalkForwardWindow, ...]:
    start, end = _aware_utc(data_start), _aware_utc(data_end)
    if end <= start:
        raise ValueError("WFO_DATA_WINDOW_INVALID")
    train_delta = timedelta(days=policy.training_days)
    oos_delta = timedelta(days=policy.oos_days)
    cursor = start
    folds: list[WalkForwardWindow] = []
    while cursor + train_delta + oos_delta <= end:
        train_end = cursor + train_delta
        folds.append(
            WalkForwardWindow(
                train_start=cursor,
                train_end=train_end,
                oos_start=train_end,
                oos_end=train_end + oos_delta,
            )
        )
        cursor += timedelta(days=policy.step_days)
    return tuple(folds)


def summarize_net_r(values: Sequence[float]) -> NetRMetrics:
    returns = [float(value) for value in values]
    if any(not math.isfinite(value) for value in returns):
        raise ValueError("WFO_NET_R_NONFINITE")
    if not returns:
        return NetRMetrics(0, None, None, None, None)
    total_wins = sum(value for value in returns if value > 0)
    total_losses = -sum(value for value in returns if value < 0)
    profit_factor = total_wins / total_losses if total_losses > 0 else None
    equity = peak = max_drawdown = 0.0
    for value in returns:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return NetRMetrics(
        trade_count=len(returns),
        net_expectancy_r=mean(returns),
        profit_factor=profit_factor,
        max_drawdown_r=max_drawdown,
        win_rate=sum(value > 0 for value in returns) / len(returns),
    )


def _parameter_sets(
    grid: Mapping[str, Sequence[Any]],
    *,
    max_parameter_sets: int,
) -> tuple[ParameterSet, ...]:
    allowed = {
        "lookback_bars",
        "min_sweep_ticks",
        "max_reclaim_bars",
        "displacement_filter",
        "ema_atr_filter",
    }
    if set(grid) != allowed:
        raise ValueError("WFO_PARAMETER_GRID_FIELDS_INVALID")
    keys = sorted(allowed)
    values = [tuple(grid[key]) for key in keys]
    if any(not value for value in values):
        raise ValueError("WFO_PARAMETER_GRID_EMPTY")
    if math.prod(len(value) for value in values) > max_parameter_sets:
        raise ValueError("WFO_PARAMETER_GRID_EXCEEDS_MAXIMUM")
    result: list[ParameterSet] = []
    seen: set[str] = set()
    for combination in product(*values):
        raw = dict(zip(keys, combination))
        if type(raw["lookback_bars"]) is not int or raw["lookback_bars"] < 3:
            raise ValueError("WFO_LOOKBACK_PARAMETER_INVALID")
        if type(raw["max_reclaim_bars"]) is not int or raw["max_reclaim_bars"] < 1:
            raise ValueError("WFO_RECLAIM_PARAMETER_INVALID")
        if (
            isinstance(raw["min_sweep_ticks"], bool)
            or not math.isfinite(float(raw["min_sweep_ticks"]))
            or float(raw["min_sweep_ticks"]) <= 0
        ):
            raise ValueError("WFO_SWEEP_PARAMETER_INVALID")
        if type(raw["displacement_filter"]) is not bool or type(raw["ema_atr_filter"]) is not bool:
            raise ValueError("WFO_FILTER_PARAMETER_INVALID")
        item = ParameterSet(
            raw["lookback_bars"],
            float(raw["min_sweep_ticks"]),
            raw["max_reclaim_bars"],
            raw["displacement_filter"],
            raw["ema_atr_filter"],
        )
        key = json.dumps(item.as_dict(), sort_keys=True, separators=(",", ":"))
        if key not in seen:
            result.append(item)
            seen.add(key)
    if not result:
        raise ValueError("WFO_PARAMETER_GRID_NO_VALID_COMBINATIONS")
    return tuple(result)


def _config_for(base: ThreeSixtyNineMSNRConfig, params: ParameterSet) -> ThreeSixtyNineMSNRConfig:
    msnr = replace(
        base.msnr_config,
        lookback_bars=params.lookback_bars,
        min_sweep_ticks=params.min_sweep_ticks,
        max_reclaim_bars=params.max_reclaim_bars,
    )
    return replace(
        base,
        msnr_config=msnr,
        displacement_filter=params.displacement_filter,
        ema_atr_filter=params.ema_atr_filter,
    )


def _bar_time(bar: StrategyBar) -> datetime:
    try:
        stamp = datetime.fromisoformat(bar.timestamp_utc.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("WFO_BAR_TIMESTAMP_INVALID") from exc
    return _aware_utc(stamp)


def calculate_normalized_bars_sha256(bars: Sequence[StrategyBar]) -> str:
    """Hash the exact normalized OHLC/time payload consumed by the simulator."""
    payload = [
        {
            "timestamp_utc": bar.timestamp_utc,
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": None if bar.volume is None else float(bar.volume),
            "session_id": bar.session_id,
        }
        for bar in bars
    ]
    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def calculate_protected_swings_sha256(
    swings: Mapping[int, ProtectedSwing],
    bars: Sequence[StrategyBar],
    *,
    timeframe_seconds: int,
) -> str:
    """Hash each confirmed swing annotation and bind it to a dataset bar index."""
    payload = []
    for index, swing in sorted(swings.items(), key=lambda item: item[0]):
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(bars) - 1:
            raise ValueError("WFO_PROTECTED_SWING_INDEX_INVALID")
        if not isinstance(swing, ProtectedSwing):
            raise ValueError("WFO_PROTECTED_SWING_RECORD_INVALID")
        known_opens = {bar.timestamp_utc for bar in bars[:index + 1]}
        known_closes = {
            (bar_close_timestamp(_bar_time(bar), timeframe_seconds)).isoformat()
            for bar in bars[:index + 1]
        }
        if swing.pivot_timestamp_utc not in known_opens:
            raise ValueError("WFO_PROTECTED_SWING_PIVOT_NOT_IN_DATASET")
        if swing.last_input_bar_timestamp_utc not in known_opens:
            raise ValueError("WFO_PROTECTED_SWING_INPUT_NOT_IN_DATASET")
        if (
            swing.confirmation_timestamp_utc not in known_opens
            and _aware_utc(datetime.fromisoformat(
                swing.confirmation_timestamp_utc.replace("Z", "+00:00")
            )).isoformat() not in known_closes
        ):
            raise ValueError("WFO_PROTECTED_SWING_CONFIRMATION_NOT_IN_DATASET")
        payload.append({
            "signal_bar_index": index,
            "direction": swing.direction,
            "anchor_price": float(swing.anchor_price),
            "pivot_timestamp_utc": swing.pivot_timestamp_utc,
            "confirmation_timestamp_utc": swing.confirmation_timestamp_utc,
            "source_rule_id": swing.source_rule_id,
            "last_input_bar_timestamp_utc": swing.last_input_bar_timestamp_utc,
        })
    if not payload:
        raise ValueError("WFO_CONFIRMED_SWINGS_MISSING")
    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def calculate_historical_cost_profiles_sha256(
    profiles: Sequence[InstrumentCostProfile],
    *,
    instrument_id: str,
) -> str:
    """Hash all numeric and provenance fields of the historical cost series."""
    payload = []
    seen: set[tuple[str, str]] = set()
    for profile in profiles:
        if profile.instrument_id != instrument_id:
            raise ValueError("WFO_COST_INSTRUMENT_MISMATCH")
        if profile.return_basis != "UNDERLYING_PRICE_NOTIONAL":
            raise ValueError("WFO_COST_RETURN_BASIS_MISMATCH")
        if not profile.verified or not profile.slippage_excludes_spread:
            raise ValueError("WFO_COST_PROFILE_NOT_VERIFIED")
        key = (profile.instrument_id, profile.observed_at_utc)
        if key in seen:
            raise ValueError("WFO_COST_PROFILE_DUPLICATE_OBSERVATION")
        seen.add(key)
        validation_time = _aware_utc(
            datetime.fromisoformat(profile.observed_at_utc.replace("Z", "+00:00"))
        )
        errors = profile.validate(now=validation_time, require_verified=True)
        if errors:
            raise ValueError("WFO_COST_PROFILE_INVALID")
        payload.append({
            "instrument_id": profile.instrument_id,
            "instrument_type": profile.instrument_type,
            "return_basis": profile.return_basis,
            "spread_cost_bps_round_trip": profile.spread_cost_bps_round_trip,
            "slippage_cost_bps_round_trip": profile.slippage_cost_bps_round_trip,
            "commission_bps_round_trip": profile.commission_bps_round_trip,
            "other_fees_bps_round_trip": profile.other_fees_bps_round_trip,
            "source": profile.source,
            "observed_at_utc": profile.observed_at_utc,
            "verified": profile.verified,
            "slippage_excludes_spread": profile.slippage_excludes_spread,
            "max_age_seconds": profile.max_age_seconds,
        })
    if not payload:
        raise ValueError("WFO_HISTORICAL_COST_PROFILES_MISSING")
    payload.sort(key=lambda row: (row["instrument_id"], row["observed_at_utc"], row["source"]))
    return sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _validate_continuity(bars: Sequence[StrategyBar], timeframe_seconds: int) -> None:
    previous = None
    for bar in bars:
        current = _bar_time(bar)
        if previous is not None:
            delta = (current - previous).total_seconds()
            if delta != timeframe_seconds:
                raise ValueError("WFO_DATA_GAP_OR_DUPLICATE_DETECTED")
        previous = current


def select_historical_cost_profile(
    profiles: Sequence[InstrumentCostProfile],
    *,
    instrument_id: str,
    entry_timestamp: datetime,
) -> InstrumentCostProfile:
    """Select the latest verified cost observation known at entry time.

    Future observations are never used; missing or stale cost coverage blocks.
    """
    entry = _aware_utc(entry_timestamp)
    eligible: list[tuple[datetime, InstrumentCostProfile]] = []
    seen: set[datetime] = set()
    for profile in profiles:
        if profile.instrument_id != instrument_id:
            continue
        if profile.return_basis != "UNDERLYING_PRICE_NOTIONAL":
            continue
        try:
            observed = datetime.fromisoformat(
                profile.observed_at_utc.replace("Z", "+00:00")
            )
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("WFO_COST_PROFILE_TIMESTAMP_INVALID") from exc
        observed = _aware_utc(observed)
        if observed > entry:
            continue
        if observed in seen:
            raise ValueError("WFO_COST_PROFILE_DUPLICATE_OBSERVATION")
        seen.add(observed)
        if not profile.validate(now=entry, require_verified=True):
            eligible.append((observed, profile))
    if not eligible:
        raise ValueError("WFO_HISTORICAL_COST_PROFILE_MISSING_OR_STALE")
    return max(eligible, key=lambda item: item[0])[1]


def summarize_regime_cells(
    trades: Sequence[SimulatedTrade],
    expected_regimes: Sequence[str],
    *,
    minimum_trades: int,
    minimum_expectancy_r: float,
    minimum_profit_factor: float,
    maximum_drawdown_r: float,
) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
    """Gate every configured regime independently; aggregate results cannot hide a weak cell."""
    cells: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    observed = {trade.regime for trade in trades}
    for regime in expected_regimes:
        values = [
            float(trade.net_r)
            for trade in trades
            if trade.regime == regime and trade.net_r is not None
        ]
        metrics = summarize_net_r(values)
        cells[regime] = metrics.__dict__
        if metrics.trade_count < minimum_trades:
            failures.append(
                f"REGIME_CELL_UNDERPOWERED:{regime}:{metrics.trade_count}"
            )
        if (
            metrics.net_expectancy_r is None
            or metrics.net_expectancy_r <= minimum_expectancy_r
        ):
            failures.append(f"REGIME_CELL_NONPOSITIVE_EXPECTANCY:{regime}")
        if (
            metrics.profit_factor is None
            or metrics.profit_factor < minimum_profit_factor
        ):
            failures.append(f"REGIME_CELL_PROFIT_FACTOR_BELOW_THRESHOLD:{regime}")
        if (
            metrics.max_drawdown_r is None
            or metrics.max_drawdown_r > maximum_drawdown_r
        ):
            failures.append(f"REGIME_CELL_MAX_DRAWDOWN_ABOVE_THRESHOLD:{regime}")
    for regime in sorted(observed - set(expected_regimes)):
        failures.append(f"UNREGISTERED_REGIME_OBSERVED:{regime}")
    return cells, tuple(failures)


def _trades_for_window(
    bars: Sequence[StrategyBar],
    swings: Mapping[int, ProtectedSwing],
    *,
    window_start: datetime,
    window_end: datetime,
    config: ThreeSixtyNineMSNRConfig,
    timeframe_seconds: int,
    cost_profiles: Sequence[InstrumentCostProfile],
) -> tuple[SimulatedTrade, ...]:
    if len(bars) < 2:
        return ()
    times = [_bar_time(bar) for bar in bars]
    end_index = next((i for i, stamp in enumerate(times) if stamp >= window_end), len(bars))
    next_free_index = 0
    warmup = max(
        config.msnr_config.lookback_bars + config.msnr_config.max_reclaim_bars + 2,
        config.regime_config.lookback_bars + 2,
        21 if config.ema_atr_filter else 4,
    )
    trades: list[SimulatedTrade] = []
    for index in range(warmup, min(end_index - 1, len(bars) - 1)):
        if index < next_free_index:
            continue
        swing = swings.get(index)
        if swing is None:
            continue
        signal_close = bar_close_timestamp(times[index], timeframe_seconds)
        if not (window_start <= signal_close < window_end):
            continue
        if not signal_close_is_eligible(signal_close):
            continue
        prefix_start = max(0, index - warmup + 1)
        candidate = evaluate_369_msnr_candidate(
            bars[prefix_start:index + 2],
            timeframe_seconds=timeframe_seconds,
            protected_swing=swing,
            config=config,
        )
        if candidate is None:
            continue
        entry_time = _aware_utc(
            datetime.fromisoformat(candidate.entry_timestamp_utc.replace("Z", "+00:00"))
        )
        historical_profile = select_historical_cost_profile(
            cost_profiles,
            instrument_id=config.instrument_id,
            entry_timestamp=entry_time,
        )
        trade = simulate_candidate(
            candidate,
            bars[index + 1:end_index],
            cost_profile=historical_profile,
            tick_size=config.tick_size,
            as_of=entry_time,
        )
        if trade.complete and trade.net_r is not None:
            trades.append(trade)
            exit_index = next(
                (i for i, bar in enumerate(bars) if bar.timestamp_utc == trade.exit_bar_timestamp_utc),
                index + 1,
            )
            next_free_index = exit_index + 1
    return tuple(trades)


def _bootstrap_ci(
    trades: Sequence[SimulatedTrade],
    *,
    replicates: int,
    seed: int,
) -> tuple[float | None, float | None]:
    """Day-block bootstrap: sample full UTC-day blocks to retain within-day ordering."""
    by_day: dict[str, list[float]] = {}
    for trade in trades:
        if trade.net_r is not None:
            day = _aware_utc(
                datetime.fromisoformat(trade.entry_timestamp_utc.replace("Z", "+00:00"))
            ).date().isoformat()
            by_day.setdefault(day, []).append(float(trade.net_r))
    days = sorted(by_day)
    if not days:
        return None, None
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(replicates):
        selected = [days[rng.randrange(len(days))] for _ in days]
        sample = [value for day in selected for value in by_day[day]]
        means.append(mean(sample))
    means.sort()
    low = means[int(0.025 * len(means))]
    high = means[min(len(means) - 1, int(0.975 * len(means)))]
    return low, high


def _score(metrics: NetRMetrics) -> tuple[float, float, float, int]:
    return (
        metrics.net_expectancy_r if metrics.net_expectancy_r is not None else -math.inf,
        metrics.profit_factor if metrics.profit_factor is not None else -math.inf,
        -(metrics.max_drawdown_r if metrics.max_drawdown_r is not None else math.inf),
        metrics.trade_count,
    )


def run_369_walk_forward(
    bars: Sequence[StrategyBar],
    protected_swings: Mapping[int, ProtectedSwing],
    *,
    base_config: ThreeSixtyNineMSNRConfig,
    timeframe_seconds: int,
    cost_profiles: Sequence[InstrumentCostProfile],
    policy: WalkForwardConfig,
    parameter_grid: Mapping[str, Sequence[Any]],
    normalized_bars_sha256: str,
    dataset_source: str,
    code_commit: str,
) -> dict[str, Any]:
    """Run rolling train/select/OOS evaluation with disjoint OOS windows."""
    _validate_bars(bars)
    if not base_config.instrument_mapping_verified:
        raise ValueError("WFO_INSTRUMENT_MAPPING_UNVERIFIED")
    if type(timeframe_seconds) is not int or timeframe_seconds not in {60, 900}:
        raise ValueError("WFO_TIMEFRAME_UNSUPPORTED")
    _validate_continuity(bars, timeframe_seconds)
    actual_bars_sha256 = calculate_normalized_bars_sha256(bars)
    if not re.fullmatch(r"[0-9a-f]{64}", str(normalized_bars_sha256)):
        raise ValueError("WFO_DATASET_SHA256_INVALID")
    if normalized_bars_sha256 != actual_bars_sha256:
        raise ValueError("WFO_NORMALIZED_DATASET_HASH_MISMATCH")
    if not dataset_source.strip() or not re.fullmatch(r"[0-9a-f]{40}", str(code_commit)):
        raise ValueError("WFO_PROVENANCE_MISSING")
    if not protected_swings:
        raise ValueError("WFO_CONFIRMED_SWINGS_MISSING")
    protected_swings_sha256 = calculate_protected_swings_sha256(
        protected_swings,
        bars,
        timeframe_seconds=timeframe_seconds,
    )
    if not cost_profiles:
        raise ValueError("WFO_HISTORICAL_COST_PROFILES_MISSING")
    historical_cost_profiles_sha256 = calculate_historical_cost_profiles_sha256(
        cost_profiles,
        instrument_id=base_config.instrument_id,
    )
    for profile in cost_profiles:
        if profile.instrument_id != base_config.instrument_id:
            raise ValueError("WFO_COST_INSTRUMENT_MISMATCH")
        if profile.return_basis != "UNDERLYING_PRICE_NOTIONAL":
            raise ValueError("WFO_COST_RETURN_BASIS_MISMATCH")
        if not profile.verified or not profile.slippage_excludes_spread:
            raise ValueError("WFO_COST_PROFILE_NOT_VERIFIED")

    data_start = _bar_time(bars[0])
    data_end = _bar_time(bars[-1]) + timedelta(seconds=timeframe_seconds)
    windows = build_rolling_windows(data_start, data_end, policy)
    if not windows:
        raise ValueError("WFO_NOT_ENOUGH_HISTORY_FOR_ONE_FOLD")
    parameters = _parameter_sets(
        parameter_grid,
        max_parameter_sets=policy.max_parameter_sets,
    )
    folds: list[dict[str, Any]] = []
    oos_trades: list[SimulatedTrade] = []

    for fold_index, window in enumerate(windows, start=1):
        train_options = []
        for parameter in parameters:
            strategy_config = _config_for(base_config, parameter)
            training_trades = _trades_for_window(
                bars, protected_swings,
                window_start=window.train_start, window_end=window.train_end,
                config=strategy_config, timeframe_seconds=timeframe_seconds,
                cost_profiles=cost_profiles,
            )
            train_metrics = summarize_net_r([
                trade.net_r for trade in training_trades if trade.net_r is not None
            ])
            if train_metrics.trade_count >= policy.minimum_training_trades:
                train_options.append((parameter, train_metrics))
        selected = max(train_options, key=lambda option: _score(option[1])) if train_options else None
        if selected is None:
            folds.append({
                "fold": fold_index,
                "selection_status": "NO_TRAINING_CONFIGURATION_MET_MINIMUM_SAMPLE",
                "selected_parameters": None,
                "oos_trade_count": 0,
                "train_start_utc": window.train_start.isoformat(),
                "train_end_utc": window.train_end.isoformat(),
                "oos_start_utc": window.oos_start.isoformat(),
                "oos_end_utc": window.oos_end.isoformat(),
            })
            continue
        selected_parameters, train_metrics = selected
        oos_config = _config_for(base_config, selected_parameters)
        fold_oos_trades = _trades_for_window(
            bars, protected_swings,
            window_start=window.oos_start, window_end=window.oos_end,
            config=oos_config, timeframe_seconds=timeframe_seconds,
            cost_profiles=cost_profiles,
        )
        oos_trades.extend(fold_oos_trades)
        oos_metrics = summarize_net_r([
            trade.net_r for trade in fold_oos_trades if trade.net_r is not None
        ])
        folds.append({
            "fold": fold_index,
            "selection_status": "TRAINED_AND_FROZEN",
            "selected_parameters": selected_parameters.as_dict(),
            "training_metrics": train_metrics.__dict__,
            "oos_metrics": oos_metrics.__dict__,
            "oos_trade_count": oos_metrics.trade_count,
            "train_start_utc": window.train_start.isoformat(),
            "train_end_utc": window.train_end.isoformat(),
            "oos_start_utc": window.oos_start.isoformat(),
            "oos_end_utc": window.oos_end.isoformat(),
        })

    metrics = summarize_net_r([trade.net_r for trade in oos_trades if trade.net_r is not None])
    ci_low, ci_high = _bootstrap_ci(
        oos_trades, replicates=policy.bootstrap_replicates, seed=policy.random_seed
    )
    failures: list[str] = []
    failures.append("PROTECTED_SWING_RULE_NOT_INDEPENDENTLY_VERIFIED")
    if not oos_trades:
        failures.append("OOS_TRADES_MISSING")
    if metrics.trade_count < policy.minimum_oos_trades:
        failures.append("OOS_MINIMUM_TRADES_NOT_MET")
    if metrics.net_expectancy_r is None or metrics.net_expectancy_r <= policy.minimum_net_expectancy_r:
        failures.append("OOS_NET_EXPECTANCY_NOT_POSITIVE")
    if metrics.profit_factor is None or metrics.profit_factor < policy.minimum_profit_factor:
        failures.append("OOS_PROFIT_FACTOR_BELOW_THRESHOLD")
    if metrics.max_drawdown_r is None or metrics.max_drawdown_r > policy.maximum_drawdown_r:
        failures.append("OOS_MAX_DRAWDOWN_ABOVE_THRESHOLD")
    if ci_low is None or ci_low <= 0:
        failures.append("OOS_BOOTSTRAP_LOWER_BOUND_NOT_POSITIVE")
    regime_cells, regime_failures = summarize_regime_cells(
        oos_trades,
        base_config.msnr_config.allowed_regimes,
        minimum_trades=policy.minimum_oos_trades,
        minimum_expectancy_r=policy.minimum_net_expectancy_r,
        minimum_profit_factor=policy.minimum_profit_factor,
        maximum_drawdown_r=policy.maximum_drawdown_r,
    )
    failures.extend(regime_failures)
    if any(fold["selection_status"] != "TRAINED_AND_FROZEN" for fold in folds):
        failures.append("ONE_OR_MORE_WALK_FORWARD_FOLDS_UNSELECTED")

    config_payload = {
        "strategy_id": "THREE_SIXTY_NINE_MSNR",
        "version": base_config.version,
        "timeframe_seconds": timeframe_seconds,
        "base_msnr": {
            "lookback_bars": base_config.msnr_config.lookback_bars,
            "min_sweep_ticks": base_config.msnr_config.min_sweep_ticks,
            "max_reclaim_bars": base_config.msnr_config.max_reclaim_bars,
        },
        "parameter_grid": {key: list(value) for key, value in sorted(parameter_grid.items())},
        "walk_forward_policy": policy.__dict__,
        "normalized_bars_sha256": actual_bars_sha256,
        "protected_swings_sha256": protected_swings_sha256,
        "historical_cost_profiles_sha256": historical_cost_profiles_sha256,
    }
    config_hash = sha256(
        json.dumps(config_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return {
        "schema": "aurelia.369_msnr.walk_forward.v1",
        "strategy_id": "THREE_SIXTY_NINE_MSNR",
        "strategy_version": base_config.version,
        "instrument_id": base_config.instrument_id,
        "timeframe_seconds": timeframe_seconds,
        "regime": "ALL_MARKET",
        "dataset_source": dataset_source,
        "normalized_bars_sha256": actual_bars_sha256,
        "protected_swings_sha256": protected_swings_sha256,
        "historical_cost_profiles_sha256": historical_cost_profiles_sha256,
        "normalized_bar_count": len(bars),
        "data_start_utc": data_start.isoformat(),
        "data_end_utc": data_end.isoformat(),
        "code_commit": code_commit,
        "config_hash": config_hash,
        "walk_forward_folds": folds,
        "multiple_testing": {
            "registered_parameter_sets": len(parameters),
            "maximum_parameter_sets": policy.max_parameter_sets,
            "total_training_trials": len(parameters) * len(windows),
            "oos_reuse_count": 0,
            "selection_rule": "MAX_NET_EXPECTANCY_R_THEN_PROFIT_FACTOR_THEN_LOWEST_DRAWDOWN",
        },
        "oos_metrics": metrics.__dict__,
        "oos_regime_cells": regime_cells,
        "oos_bootstrap_95pct_ci": {"lower": ci_low, "upper": ci_high},
        "oos_trade_count": metrics.trade_count,
        "qualification_status": "RESEARCH_QUALIFIED" if not failures else "RESEARCH_ONLY_UNQUALIFIED",
        "qualification_failures": failures,
        "strategy_live_eligible": False,
        "capital_authority": False,
        "order_submission_permitted": False,
        "live_execution": False,
        "trade_evidence": [{
            "signal_close_timestamp_utc": trade.signal_close_timestamp_utc,
            "entry_timestamp_utc": trade.entry_timestamp_utc,
            "exit_bar_timestamp_utc": trade.exit_bar_timestamp_utc,
            "direction": trade.direction,
            "regime": trade.regime,
            "entry_price": trade.entry_price,
            "stop_price": trade.stop_price,
            "target_price": trade.target_price,
            "exit_price": trade.exit_price,
            "gross_r": trade.gross_r,
            "net_r": trade.net_r,
            "exit_reason": trade.exit_reason,
            "cost_profile_source": trade.cost_profile_source,
            "cost_profile_observed_at_utc": trade.cost_profile_observed_at_utc,
        } for trade in oos_trades],
    }
