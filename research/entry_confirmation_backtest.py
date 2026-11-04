from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from math import isfinite
from statistics import fmean
from typing import Mapping, Sequence

from research.labs.deterministic_intraday_strategies import (
    CycleMarkerConfig,
    MSNRConfirmationConfig,
    MSNRConfirmationVerdict,
    RegimeConfig,
    StrategyBar,
    _utc,
    evaluate_msnr_entry_confirmation,
)


@dataclass(frozen=True)
class ExitPolicy:
    """Price-space exit policy. The hold period must be supplied explicitly."""

    max_hold_bars: int
    breakeven_trigger_r: float | None
    trailing_method: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_hold_bars, bool)
            or not isinstance(self.max_hold_bars, int)
            or self.max_hold_bars < 1
        ):
            raise ValueError("MAX_HOLD_BARS_REQUIRED")
        if self.breakeven_trigger_r is not None and (
            isinstance(self.breakeven_trigger_r, bool)
            or not isinstance(self.breakeven_trigger_r, (int, float))
            or not isfinite(float(self.breakeven_trigger_r))
            or float(self.breakeven_trigger_r) <= 0
        ):
            raise ValueError("BREAKEVEN_TRIGGER_INVALID")
        if self.trailing_method != "none":
            raise ValueError("TRAILING_STOP_METHOD_UNSUPPORTED")


@dataclass(frozen=True)
class BacktestCostModel:
    """Underlying price-space cost model, not a Deriv contract payout model."""

    tick_size: float
    slippage_ticks_per_side: float
    commission_price_units_round_trip: float
    cost_source: str
    provenance_status: str = "PROVISIONAL"

    def __post_init__(self) -> None:
        values = (
            self.tick_size,
            self.slippage_ticks_per_side,
            self.commission_price_units_round_trip,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(float(value))
            for value in values
        ):
            raise ValueError("COST_ASSUMPTION_INVALID")
        if self.tick_size <= 0 or self.slippage_ticks_per_side < 0 or self.commission_price_units_round_trip < 0:
            raise ValueError("COST_ASSUMPTION_INVALID")
        if not isinstance(self.cost_source, str) or not self.cost_source.strip():
            raise ValueError("COST_SOURCE_REQUIRED")
        if self.provenance_status not in {"PROVISIONAL", "VERIFIED"}:
            raise ValueError("COST_PROVENANCE_STATUS_INVALID")


@dataclass(frozen=True)
class TradeSimulation:
    direction: str
    signal_index: int
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    initial_risk_price_units: float
    gross_r_multiple: float
    net_r_multiple: float
    exit_reason: str
    capital_authority: bool = False
    order_submission_permitted: bool = False


@dataclass(frozen=True)
class RiskMetrics:
    trade_count: int
    expectancy_r: float
    profit_factor: float | None
    max_drawdown_r: float
    r_min: float
    r_p05: float
    r_median: float
    r_p95: float
    r_max: float


@dataclass(frozen=True)
class FilterEfficacy:
    accepted_signal_count: int
    rejected_signal_count: int
    accepted_loss_rate: float | None
    rejected_loss_rate: float | None
    filter_efficacy_ratio: float | None
    status: str


@dataclass(frozen=True)
class ChronologicalSplit:
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    test_start: int
    test_end: int
    embargo_bars: int


@dataclass(frozen=True)
class MSNRBacktestReport:
    status: str
    accepted_trades: tuple[TradeSimulation, ...]
    rejected_counterfactuals: tuple[TradeSimulation, ...]
    accepted_metrics: RiskMetrics | None
    rejected_metrics: RiskMetrics | None
    filter_efficacy: FilterEfficacy
    rejection_reasons: Mapping[str, int]
    source_dataset_sha256: str
    cost_source: str
    cost_provenance_status: str
    accounting_basis: str = "UNDERLYING_PRICE_SPACE_R_MULTIPLES_ONLY"
    capital_authority: bool = False
    order_submission_permitted: bool = False


def _percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if not sorted_values:
        raise ValueError("PERCENTILE_REQUIRES_VALUES")
    if not 0 <= percentile <= 1:
        raise ValueError("PERCENTILE_OUT_OF_RANGE")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = percentile * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return (
        float(sorted_values[lower]) * (1 - fraction)
        + float(sorted_values[upper]) * fraction
    )


def compute_risk_metrics(r_multiples: Sequence[float]) -> RiskMetrics:
    values = [float(value) for value in r_multiples]
    if not values or any(not isfinite(value) for value in values):
        raise ValueError("R_MULTIPLE_SAMPLE_INVALID")
    ordered = sorted(values)
    positive = sum(value for value in values if value > 0)
    negative = abs(sum(value for value in values if value < 0))
    profit_factor = positive / negative if negative > 0 else None

    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)

    return RiskMetrics(
        trade_count=len(values),
        expectancy_r=fmean(values),
        profit_factor=profit_factor,
        max_drawdown_r=max_drawdown,
        r_min=ordered[0],
        r_p05=_percentile(ordered, 0.05),
        r_median=_percentile(ordered, 0.50),
        r_p95=_percentile(ordered, 0.95),
        r_max=ordered[-1],
    )


def evaluate_filter_efficacy(
    *,
    accepted_r_multiples: Sequence[float],
    rejected_counterfactual_r_multiples: Sequence[float],
) -> FilterEfficacy:
    accepted = [float(value) for value in accepted_r_multiples]
    rejected = [float(value) for value in rejected_counterfactual_r_multiples]
    if any(not isfinite(x) for x in accepted + rejected):
        raise ValueError("FILTER_EFFICACY_SAMPLE_INVALID")
    if not accepted or not rejected:
        return FilterEfficacy(
            len(accepted), len(rejected), None, None, None,
            "INSUFFICIENT_COUNTERFACTUAL_SAMPLE",
        )

    accepted_loss_rate = sum(value <= 0 for value in accepted) / len(accepted)
    rejected_loss_rate = sum(value <= 0 for value in rejected) / len(rejected)
    if accepted_loss_rate == 0:
        ratio = None
        status = "NO_ACCEPTED_LOSSES_RATIO_UNDEFINED"
    else:
        ratio = rejected_loss_rate / accepted_loss_rate
        status = "COMPARABLE_COUNTERFACTUAL_POOLS"
    return FilterEfficacy(
        len(accepted),
        len(rejected),
        accepted_loss_rate,
        rejected_loss_rate,
        ratio,
        status,
    )


def chronological_split_indices(
    observation_count: int,
    *,
    embargo_bars: int,
) -> ChronologicalSplit:
    if (
        isinstance(observation_count, bool)
        or not isinstance(observation_count, int)
        or observation_count < 10
    ):
        raise ValueError("CHRONOLOGICAL_SAMPLE_TOO_SMALL")
    if (
        isinstance(embargo_bars, bool)
        or not isinstance(embargo_bars, int)
        or embargo_bars < 0
    ):
        raise ValueError("CHRONOLOGICAL_EMBARGO_INVALID")

    train_end = int(observation_count * 0.60)
    validation_end = int(observation_count * 0.80)
    validation_start = train_end + embargo_bars
    test_start = validation_end + embargo_bars
    if validation_start >= validation_end or test_start >= observation_count:
        raise ValueError("CHRONOLOGICAL_EMBARGO_CONSUMES_SPLIT")
    return ChronologicalSplit(
        train_start=0,
        train_end=train_end,
        validation_start=validation_start,
        validation_end=validation_end,
        test_start=test_start,
        test_end=observation_count,
        embargo_bars=embargo_bars,
    )


def simulate_trade(
    bars: Sequence[StrategyBar],
    *,
    signal_index: int,
    verdict: MSNRConfirmationVerdict,
    exit_policy: ExitPolicy,
    costs: BacktestCostModel,
) -> TradeSimulation:
    """Use next-bar open; if stop and target touch inside the same bar, stop wins."""
    if not isinstance(verdict, MSNRConfirmationVerdict) or not verdict.signal_valid:
        raise ValueError("VALID_SIGNAL_VERDICT_REQUIRED")
    if verdict.direction not in {"LONG", "SHORT"}:
        raise ValueError("TRADE_DIRECTION_INVALID")
    if (
        isinstance(signal_index, bool)
        or not isinstance(signal_index, int)
        or signal_index < 0
        or signal_index + 1 >= len(bars)
    ):
        raise ValueError("NEXT_BAR_ENTRY_UNAVAILABLE")
    if verdict.stop_reference_price is None or verdict.target_reference_price is None:
        raise ValueError("STOP_AND_TARGET_REQUIRED")

    entry_index = signal_index + 1
    signal_bar = bars[signal_index]
    entry_bar = bars[entry_index]
    direction_factor = 1.0 if verdict.direction == "LONG" else -1.0
    slippage = float(costs.tick_size) * float(costs.slippage_ticks_per_side)
    entry_price = (
        float(entry_bar.open) + slippage
        if verdict.direction == "LONG"
        else float(entry_bar.open) - slippage
    )
    stop = float(verdict.stop_reference_price)
    target = float(verdict.target_reference_price)
    initial_risk = direction_factor * (entry_price - stop)
    reward_distance = direction_factor * (target - entry_price)
    if not isfinite(initial_risk) or initial_risk <= 0 or reward_distance <= 0:
        raise ValueError("INITIAL_RISK_INVALID")

    active_stop = stop
    exit_raw: float | None = None
    exit_reason = ""
    required_last_index = entry_index + exit_policy.max_hold_bars - 1
    last_index = min(required_last_index, len(bars) - 1)

    for index in range(entry_index, last_index + 1):
        current = bars[index]
        if verdict.direction == "LONG":
            if current.open <= active_stop:
                exit_raw, exit_reason = float(current.open), "STOP_GAP"
            elif current.open >= target:
                exit_raw, exit_reason = target, "TARGET"
            else:
                stop_hit = current.low <= active_stop
                target_hit = current.high >= target
                if stop_hit and target_hit:
                    exit_raw, exit_reason = active_stop, "STOP"
                elif stop_hit:
                    exit_raw, exit_reason = active_stop, "STOP"
                elif target_hit:
                    exit_raw, exit_reason = target, "TARGET"
        else:
            if current.open >= active_stop:
                exit_raw, exit_reason = float(current.open), "STOP_GAP"
            elif current.open <= target:
                exit_raw, exit_reason = target, "TARGET"
            else:
                stop_hit = current.high >= active_stop
                target_hit = current.low <= target
                if stop_hit and target_hit:
                    exit_raw, exit_reason = active_stop, "STOP"
                elif stop_hit:
                    exit_raw, exit_reason = active_stop, "STOP"
                elif target_hit:
                    exit_raw, exit_reason = target, "TARGET"

        if exit_raw is not None:
            exit_index = index
            break

        if exit_policy.breakeven_trigger_r is not None:
            threshold = float(exit_policy.breakeven_trigger_r) * initial_risk
            favorable = (
                float(current.high) - entry_price
                if verdict.direction == "LONG"
                else entry_price - float(current.low)
            )
            if favorable >= threshold:
                active_stop = (
                    max(active_stop, entry_price)
                    if verdict.direction == "LONG"
                    else min(active_stop, entry_price)
                )
        exit_index = index
    if exit_raw is None:
        if required_last_index >= len(bars):
            raise ValueError("MAX_HOLD_HISTORY_INCOMPLETE")
        exit_raw = float(bars[last_index].close)
        exit_reason = "TIME_EXIT"
        exit_index = last_index

    exit_price = (
        exit_raw - slippage
        if verdict.direction == "LONG"
        else exit_raw + slippage
    )
    gross_price_pnl = direction_factor * (exit_price - entry_price)
    net_price_pnl = gross_price_pnl - float(costs.commission_price_units_round_trip)
    return TradeSimulation(
        direction=verdict.direction,
        signal_index=signal_index,
        entry_index=entry_index,
        exit_index=exit_index,
        entry_price=entry_price,
        exit_price=exit_price,
        stop_price=stop,
        target_price=target,
        initial_risk_price_units=initial_risk,
        gross_r_multiple=gross_price_pnl / initial_risk,
        net_r_multiple=net_price_pnl / initial_risk,
        exit_reason=exit_reason,
    )


def run_msnr_backtest(
    bars: Sequence[StrategyBar],
    *,
    config: MSNRConfirmationConfig,
    regime_config: RegimeConfig,
    exit_policy: ExitPolicy,
    costs: BacktestCostModel,
    higher_timeframe_bars: Sequence[StrategyBar] | None = None,
    setup_ready_times: Mapping[int, datetime] | None = None,
    cycle_config: CycleMarkerConfig | None = None,
    source_dataset_sha256: str = "LOCAL_UNPINNED",
    volume_source_verified: bool = False,
) -> MSNRBacktestReport:
    """Run causal price-space research and rejected-signal counterfactuals only."""
    if len(source_dataset_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in source_dataset_sha256.lower()
    ):
        if source_dataset_sha256 != "LOCAL_UNPINNED":
            raise ValueError("SOURCE_DATASET_SHA256_INVALID")
    if not bars:
        raise ValueError("BACKTEST_BARS_EMPTY")

    baseline_config = replace(
        config,
        require_volume_confirmation=False,
        require_htf_alignment=False,
        temporal_required=False,
        allowed_regimes=(
            "TRENDING_LOW_VOL",
            "RANGING_LOW_VOL",
            "TRENDING_HIGH_VOL",
            "RANGING_HIGH_VOL",
        ),
    )
    accepted: list[TradeSimulation] = []
    rejected: list[TradeSimulation] = []
    rejection_reasons: Counter[str] = Counter()
    next_available_signal = 0
    minimum_history = max(
        config.lookback_bars + 1,
        config.atr_period + 1,
        regime_config.lookback_bars + 2,
    )

    for signal_index in range(minimum_history - 1, len(bars) - 1):
        if signal_index < next_available_signal:
            continue
        prefix = bars[:signal_index + 1]
        base_verdict = evaluate_msnr_entry_confirmation(
            prefix,
            config=baseline_config,
            regime_config=regime_config,
        )
        if not base_verdict.signal_valid:
            continue

        signal_time = datetime.fromisoformat(
            bars[signal_index].timestamp_utc.replace("Z", "+00:00")
        )
        htf_prefix = None
        if higher_timeframe_bars is not None:
            htf_prefix = [
                item for item in higher_timeframe_bars
                if _utc(item.timestamp_utc) < _utc(bars[signal_index].timestamp_utc)
            ]
        strict_verdict = evaluate_msnr_entry_confirmation(
            prefix,
            config=config,
            regime_config=regime_config,
            higher_timeframe_bars=htf_prefix,
            volume_source_verified=volume_source_verified,
            signal_time=signal_time,
            setup_ready_time=(setup_ready_times or {}).get(signal_index),
            cycle_config=cycle_config,
        )
        if strict_verdict.signal_valid:
            trade = simulate_trade(
                bars,
                signal_index=signal_index,
                verdict=strict_verdict,
                exit_policy=exit_policy,
                costs=costs,
            )
            accepted.append(trade)
            next_available_signal = trade.exit_index + 1
        else:
            rejection_reasons[strict_verdict.reason] += 1
            trade = simulate_trade(
                bars,
                signal_index=signal_index,
                verdict=base_verdict,
                exit_policy=exit_policy,
                costs=costs,
            )
            rejected.append(trade)
            next_available_signal = trade.exit_index + 1

    accepted_metrics = (
        compute_risk_metrics([trade.net_r_multiple for trade in accepted])
        if accepted else None
    )
    rejected_metrics = (
        compute_risk_metrics([trade.net_r_multiple for trade in rejected])
        if rejected else None
    )
    efficacy = evaluate_filter_efficacy(
        accepted_r_multiples=[trade.net_r_multiple for trade in accepted],
        rejected_counterfactual_r_multiples=[trade.net_r_multiple for trade in rejected],
    )
    return MSNRBacktestReport(
        status="RESEARCH_ONLY_UNQUALIFIED",
        accepted_trades=tuple(accepted),
        rejected_counterfactuals=tuple(rejected),
        accepted_metrics=accepted_metrics,
        rejected_metrics=rejected_metrics,
        filter_efficacy=efficacy,
        rejection_reasons=dict(rejection_reasons),
        source_dataset_sha256=source_dataset_sha256,
        cost_source=costs.cost_source,
        cost_provenance_status=costs.provenance_status,
    )
