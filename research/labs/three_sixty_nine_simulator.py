from __future__ import annotations

"""Conservative research-only event simulator for 369/MSNR candidates.

Outputs underlying-price P&L only. It does not model Deriv binary-option payout
or contract purchase economics.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Sequence

from research.labs.deterministic_intraday_strategies import StrategyBar, _validate_bars
from research.labs.intraday_bias_cost_model import InstrumentCostProfile
from research.labs.three_sixty_nine_msnr import ThreeSixtyNineMSNRCandidate


@dataclass(frozen=True)
class SimulatedTrade:
    strategy_id: str
    strategy_version: str
    instrument_id: str
    direction: str
    regime: str
    signal_close_timestamp_utc: str
    entry_timestamp_utc: str
    exit_bar_timestamp_utc: str | None
    entry_price: float
    stop_price: float
    target_price: float
    exit_price: float | None
    risk_per_unit: float
    gross_pnl: float | None
    gross_r: float | None
    spread_cost: float
    slippage_cost: float
    commission_cost: float
    other_fees: float
    total_cost: float
    net_pnl: float | None
    net_r: float | None
    exit_reason: str
    complete: bool
    cost_profile_source: str
    cost_profile_observed_at_utc: str
    capital_authority: bool = False
    order_submission_permitted: bool = False


def _utc(value: str, code: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(code) from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(code)
    return stamp.astimezone(timezone.utc)


def _positive(value: object, code: str) -> float:
    if isinstance(value, bool):
        raise ValueError(code)
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(code) from exc
    if not isfinite(number) or number <= 0:
        raise ValueError(code)
    return number


def _aligned(value: float, tick_size: float) -> bool:
    try:
        ratio = Decimal(str(value)) / Decimal(str(tick_size))
    except (InvalidOperation, ZeroDivisionError):
        return False
    return ratio == ratio.to_integral_value()


def _exit_on_bar(bar: StrategyBar, direction: str, stop: float, target: float):
    if direction == "LONG":
        if bar.open <= stop:
            return "STOP_LOSS", float(bar.open)
        if bar.open >= target:
            return "TAKE_PROFIT", float(target)
        stop_hit, target_hit = bar.low <= stop, bar.high >= target
    elif direction == "SHORT":
        if bar.open >= stop:
            return "STOP_LOSS", float(bar.open)
        if bar.open <= target:
            return "TAKE_PROFIT", float(target)
        stop_hit, target_hit = bar.high >= stop, bar.low <= target
    else:
        raise ValueError("369_SIMULATION_DIRECTION_INVALID")
    if stop_hit:
        return "STOP_LOSS", float(stop)
    if target_hit:
        return "TAKE_PROFIT", float(target)
    return None


def simulate_candidate(
    candidate: ThreeSixtyNineMSNRCandidate,
    bars: Sequence[StrategyBar],
    *,
    cost_profile: InstrumentCostProfile,
    tick_size: float,
    as_of: datetime | None = None,
) -> SimulatedTrade:
    """Simulate next-open entry; ambiguous OHLC uses stop-first; costs must be verified."""
    if candidate.capital_authority or candidate.order_submission_permitted:
        raise ValueError("369_SIMULATOR_RESEARCH_AUTHORITY_VIOLATION")
    if not bars:
        raise ValueError("369_SIMULATOR_BARS_MISSING")
    _validate_bars(bars)
    tick = _positive(tick_size, "369_SIMULATOR_TICK_SIZE_INVALID")
    entry = _positive(candidate.entry_price, "369_SIMULATOR_ENTRY_INVALID")
    stop = _positive(candidate.stop_price, "369_SIMULATOR_STOP_INVALID")
    target = _positive(candidate.target_price, "369_SIMULATOR_TARGET_INVALID")
    if not all(_aligned(v, tick) for v in (entry, stop, target)):
        raise ValueError("369_SIMULATOR_PRICE_NOT_TICK_ALIGNED")
    if candidate.direction == "LONG":
        risk = entry - stop
        if target <= entry:
            raise ValueError("369_SIMULATOR_LONG_LEVELS_INVALID")
    elif candidate.direction == "SHORT":
        risk = stop - entry
        if target >= entry:
            raise ValueError("369_SIMULATOR_SHORT_LEVELS_INVALID")
    else:
        raise ValueError("369_SIMULATION_DIRECTION_INVALID")
    if not isfinite(risk) or risk <= 0:
        raise ValueError("369_SIMULATOR_RISK_INVALID")

    entry_time = _utc(candidate.entry_timestamp_utc, "369_SIMULATOR_ENTRY_TIME_INVALID")
    signal_time = _utc(candidate.signal_close_timestamp_utc, "369_SIMULATOR_SIGNAL_TIME_INVALID")
    if entry_time < signal_time:
        raise ValueError("369_SIMULATOR_ENTRY_PRECEDES_SIGNAL_CLOSE")
    entry_index = next(
        (i for i, bar in enumerate(bars) if _utc(bar.timestamp_utc, "369_SIMULATOR_BAR_TIME_INVALID") == entry_time),
        None,
    )
    if entry_index is None:
        raise ValueError("369_SIMULATOR_ENTRY_BAR_NOT_FOUND")
    tolerance = max(1e-12, tick * 1e-9)
    if abs(float(bars[entry_index].open) - entry) > tolerance:
        raise ValueError("369_SIMULATOR_ENTRY_NOT_NEXT_BAR_OPEN")

    if cost_profile.instrument_id != candidate.instrument_id:
        raise ValueError("369_SIMULATOR_COST_INSTRUMENT_MISMATCH")
    if cost_profile.return_basis != "UNDERLYING_PRICE_NOTIONAL":
        raise ValueError("369_SIMULATOR_COST_RETURN_BASIS_MISMATCH")
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("369_SIMULATOR_AS_OF_MUST_BE_AWARE")
    bps = cost_profile.total_cost_bps(now=now, require_verified=True)
    spread = entry * float(cost_profile.spread_cost_bps_round_trip) / 10_000.0
    slippage = entry * float(cost_profile.slippage_cost_bps_round_trip) / 10_000.0
    commission = entry * float(cost_profile.commission_bps_round_trip) / 10_000.0
    fees = entry * float(cost_profile.other_fees_bps_round_trip) / 10_000.0
    total = spread + slippage + commission + fees
    if abs(total - entry * bps / 10_000.0) > 1e-9:
        raise ValueError("369_SIMULATOR_COST_RECONCILIATION_FAILED")

    sign = 1.0 if candidate.direction == "LONG" else -1.0
    for bar in bars[entry_index:]:
        result = _exit_on_bar(bar, candidate.direction, stop, target)
        if result is None:
            continue
        reason, exit_price = result
        gross = sign * (exit_price - entry)
        net = gross - total
        return SimulatedTrade(
            strategy_id=candidate.strategy_id,
            strategy_version=candidate.version,
            instrument_id=candidate.instrument_id,
            direction=candidate.direction,
            regime=candidate.regime,
            signal_close_timestamp_utc=candidate.signal_close_timestamp_utc,
            entry_timestamp_utc=candidate.entry_timestamp_utc,
            exit_bar_timestamp_utc=bar.timestamp_utc,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            exit_price=exit_price,
            risk_per_unit=risk,
            gross_pnl=gross,
            gross_r=gross / risk,
            spread_cost=spread,
            slippage_cost=slippage,
            commission_cost=commission,
            other_fees=fees,
            total_cost=total,
            net_pnl=net,
            net_r=net / risk,
            exit_reason=reason,
            complete=True,
            cost_profile_source=cost_profile.source,
            cost_profile_observed_at_utc=cost_profile.observed_at_utc,
        )
    return SimulatedTrade(
        strategy_id=candidate.strategy_id,
        strategy_version=candidate.version,
        instrument_id=candidate.instrument_id,
        direction=candidate.direction,
        regime=candidate.regime,
        signal_close_timestamp_utc=candidate.signal_close_timestamp_utc,
        entry_timestamp_utc=candidate.entry_timestamp_utc,
        exit_bar_timestamp_utc=None,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        exit_price=None,
        risk_per_unit=risk,
        gross_pnl=None,
        gross_r=None,
        spread_cost=spread,
        slippage_cost=slippage,
        commission_cost=commission,
        other_fees=fees,
        total_cost=total,
        net_pnl=None,
        net_r=None,
        exit_reason="END_OF_DATA",
        complete=False,
        cost_profile_source=cost_profile.source,
        cost_profile_observed_at_utc=cost_profile.observed_at_utc,
    )
