"""Conservative, research-only event simulator for 369/MSNR candidates.

No broker, account, capital-authority, or order-routing dependencies.
Unknown or stale costs block simulation. Ambiguous OHLC bars resolve stop-first.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Sequence

from research.labs.deterministic_intraday_strategies import StrategyBar
from research.labs.intraday_bias_cost_model import InstrumentCostProfile
from research.labs.three_sixty_nine_msnr import ThreeSixtyNineMSNRCandidate


def _utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("SIMULATOR_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("SIMULATOR_TIMESTAMP_MUST_BE_AWARE")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class SimulatedTrade:
    strategy_id: str
    strategy_version: str
    instrument_id: str
    direction: str
    signal_close_timestamp_utc: str
    entry_timestamp_utc: str
    exit_timestamp_utc: str
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    gross_pnl_per_unit: float
    spread_cost_per_unit: float
    slippage_cost_per_unit: float
    commission_cost_per_unit: float
    other_fees_per_unit: float
    total_cost_per_unit: float
    net_pnl_per_unit: float
    gross_r: float
    net_r: float
    exit_reason: str
    cost_source: str
    cost_observed_at_utc: str
    capital_authority: bool = False
    order_submission_permitted: bool = False


def simulate_candidate(
    candidate: ThreeSixtyNineMSNRCandidate,
    bars: Sequence[StrategyBar],
    *,
    cost_profile: InstrumentCostProfile,
    tick_size: float,
    timeframe_seconds: int,
    now: datetime | None = None,
) -> SimulatedTrade | None:
    """Simulate one candidate using next-open entry and conservative OHLC rules.

    Costs are bps of entry notional, charged once round-trip per unit. The
    supplied cost profile must be verified, fresh, instrument-matched and use
    an underlying-price return basis. Unknown costs never default to zero.
    The last available close is an explicit END_OF_DATA exit, not an EOD exit.
    """
    if candidate.capital_authority or candidate.order_submission_permitted:
        raise ValueError("RESEARCH_CANDIDATE_AUTHORITY_FLAGS_INVALID")
    if candidate.instrument_id != cost_profile.instrument_id:
        raise ValueError("SIMULATOR_INSTRUMENT_COST_PROFILE_MISMATCH")
    if cost_profile.return_basis != "UNDERLYING_PRICE_RETURN":
        raise ValueError("SIMULATOR_COST_RETURN_BASIS_UNSUPPORTED")
    if not isfinite(float(tick_size)) or tick_size <= 0:
        raise ValueError("SIMULATOR_TICK_SIZE_INVALID")
    if type(timeframe_seconds) is not int or timeframe_seconds <= 0:
        raise ValueError("SIMULATOR_TIMEFRAME_SECONDS_INVALID")
    errors = cost_profile.validate(now=now, require_verified=True)
    if errors:
        raise ValueError("SIMULATOR_COST_PROFILE_INVALID:" + ",".join(errors))
    if not bars:
        return None

    ordered = tuple(bars)
    stamps = [_utc(bar.timestamp_utc) for bar in ordered]
    if any(right <= left for left, right in zip(stamps, stamps[1:])):
        raise ValueError("SIMULATOR_BARS_NOT_STRICTLY_CHRONOLOGICAL")
    expected_delta = timeframe_seconds
    if any((right - left).total_seconds() != expected_delta for left, right in zip(stamps, stamps[1:])):
        raise ValueError("SIMULATOR_BAR_GAP_OR_CADENCE_MISMATCH")
    for bar in ordered:
        values = (bar.open, bar.high, bar.low, bar.close)
        if not all(isfinite(float(value)) for value in values):
            raise ValueError("SIMULATOR_OHLC_NONFINITE")
        if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close) or bar.low > bar.high:
            raise ValueError("SIMULATOR_OHLC_INVARIANT_FAILED")

    signal_close_time = _utc(candidate.signal_close_timestamp_utc)
    entry_time = _utc(candidate.entry_timestamp_utc)
    if entry_time <= signal_close_time:
        raise ValueError("SIMULATOR_ENTRY_NOT_AFTER_SIGNAL_CLOSE")
    entry_index = next((i for i, stamp in enumerate(stamps) if stamp == entry_time), None)
    if entry_index is None:
        return None
    entry_bar = ordered[entry_index]
    entry = float(candidate.entry_price)
    if abs(float(entry_bar.open) - entry) > tick_size * 1e-8:
        raise ValueError("SIMULATOR_ENTRY_DOES_NOT_MATCH_NEXT_BAR_OPEN")

    direction = candidate.direction
    if direction not in {"LONG", "SHORT"}:
        raise ValueError("SIMULATOR_DIRECTION_INVALID")
    stop, target = float(candidate.stop_price), float(candidate.target_price)
    risk = entry - stop if direction == "LONG" else stop - entry
    reward = target - entry if direction == "LONG" else entry - target
    if not isfinite(risk) or risk <= 0 or not isfinite(reward) or reward <= 0:
        raise ValueError("SIMULATOR_STOP_TARGET_GEOMETRY_INVALID")

    spread_bps = float(cost_profile.spread_cost_bps_round_trip)
    slippage_bps = float(cost_profile.slippage_cost_bps_round_trip)
    commission_bps = float(cost_profile.commission_bps_round_trip)
    fees_bps = float(cost_profile.other_fees_bps_round_trip)
    notional = entry
    spread_cost = notional * spread_bps / 10000.0
    slippage_cost = notional * slippage_bps / 10000.0
    commission_cost = notional * commission_bps / 10000.0
    other_fees = notional * fees_bps / 10000.0
    total_cost = spread_cost + slippage_cost + commission_cost + other_fees

    exit_price: float | None = None
    exit_index = entry_index
    exit_reason = ""
    for i in range(entry_index, len(ordered)):
        bar = ordered[i]
        if i > entry_index:
            if direction == "LONG":
                if bar.open <= stop:
                    exit_price, exit_reason = float(bar.open), "GAP_THROUGH_STOP"
                elif bar.open >= target:
                    exit_price, exit_reason = target, "GAP_THROUGH_TARGET_CONSERVATIVE"
            else:
                if bar.open >= stop:
                    exit_price, exit_reason = float(bar.open), "GAP_THROUGH_STOP"
                elif bar.open <= target:
                    exit_price, exit_reason = target, "GAP_THROUGH_TARGET_CONSERVATIVE"
            if exit_price is not None:
                exit_index = i
                break

        stop_hit = bar.low <= stop if direction == "LONG" else bar.high >= stop
        target_hit = bar.high >= target if direction == "LONG" else bar.low <= target
        if stop_hit:
            exit_price, exit_reason, exit_index = stop, "STOP_LOSS", i
            break
        if target_hit:
            exit_price, exit_reason, exit_index = target, "TAKE_PROFIT", i
            break

    if exit_price is None:
        exit_index = len(ordered) - 1
        exit_price = float(ordered[exit_index].close)
        exit_reason = "END_OF_DATA"

    signed_move = exit_price - entry if direction == "LONG" else entry - exit_price
    gross_pnl = signed_move
    net_pnl = gross_pnl - total_cost
    gross_r = gross_pnl / risk
    net_r = net_pnl / risk
    return SimulatedTrade(
        strategy_id=candidate.strategy_id,
        strategy_version=candidate.version,
        instrument_id=candidate.instrument_id,
        direction=direction,
        signal_close_timestamp_utc=candidate.signal_close_timestamp_utc,
        entry_timestamp_utc=candidate.entry_timestamp_utc,
        exit_timestamp_utc=stamps[exit_index].isoformat(),
        entry_price=entry,
        exit_price=float(exit_price),
        stop_price=stop,
        target_price=target,
        gross_pnl_per_unit=gross_pnl,
        spread_cost_per_unit=spread_cost,
        slippage_cost_per_unit=slippage_cost,
        commission_cost_per_unit=commission_cost,
        other_fees_per_unit=other_fees,
        total_cost_per_unit=total_cost,
        net_pnl_per_unit=net_pnl,
        gross_r=gross_r,
        net_r=net_r,
        exit_reason=exit_reason,
        cost_source=cost_profile.source,
        cost_observed_at_utc=cost_profile.observed_at_utc,
        capital_authority=False,
        order_submission_permitted=False,
    )


def simulate_candidates(
    candidates: Sequence[ThreeSixtyNineMSNRCandidate],
    bars_by_symbol: dict[str, Sequence[StrategyBar]],
    *,
    cost_profiles: dict[str, InstrumentCostProfile],
    tick_sizes: dict[str, float],
    timeframe_seconds_by_symbol: dict[str, int],
    now: datetime | None = None,
) -> tuple[SimulatedTrade, ...]:
    """Run candidates independently; missing symbol evidence is rejected."""
    results: list[SimulatedTrade] = []
    for candidate in candidates:
        symbol = candidate.instrument_id
        if (symbol not in bars_by_symbol or symbol not in cost_profiles or
                symbol not in tick_sizes or symbol not in timeframe_seconds_by_symbol):
            continue
        result = simulate_candidate(
            candidate,
            bars_by_symbol[symbol],
            cost_profile=cost_profiles[symbol],
            tick_size=tick_sizes[symbol],
            timeframe_seconds=timeframe_seconds_by_symbol[symbol],
            now=now,
        )
        if result is not None:
            results.append(result)
    return tuple(results)
