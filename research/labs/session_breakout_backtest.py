"""Research-only bar-level backtest harness for US-session candidate primitives.

Input timestamps mark bar opens and must be timezone-aware. The harness supports
causal next-bar reference entries, stop/target first-touch replay, explicit OHLC
ambiguity, session NO_TRADE, time exits, optional complete cost scenarios, and
summary metrics. It cannot authorize or submit broker orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import isfinite
from typing import Literal, Mapping, Sequence
from zoneinfo import ZoneInfo

from research.labs.session_breakout_candidates import (
    BreakoutCandidate,
    OHLCBar,
    PriceRange,
    TargetMode,
    opening_range_30m_from_15m,
    opening_range_close_candidate,
    premarket_close_candidate,
    premarket_range_5m,
)

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False

NEW_YORK = ZoneInfo("America/New_York")
SESSION_FLAT_TIME = time(16, 0)
LAST_FIVE_MINUTE_OPEN = time(15, 55)


@dataclass(frozen=True)
class CostModel:
    """Round-trip costs per one contract.

    spread_round_trip_points is the total spread cost across entry and exit.
    slippage_ticks_per_side is in ticks, charged at both entry and exit.
    commission_roundtrip_usd must include all entered round-trip fees.
    An omitted cost is UNKNOWN; it is never silently interpreted as zero.
    """

    tick_size: float
    multiplier_usd_per_point: float
    spread_round_trip_points: float | None
    slippage_ticks_per_side: float | None
    commission_roundtrip_usd: float | None

    def __post_init__(self) -> None:
        if not isfinite(self.tick_size) or self.tick_size <= 0:
            raise ValueError("COST_TICK_SIZE_MUST_BE_POSITIVE")
        if not isfinite(self.multiplier_usd_per_point) or self.multiplier_usd_per_point <= 0:
            raise ValueError("COST_MULTIPLIER_MUST_BE_POSITIVE")
        for name, value in (
            ("spread_round_trip_points", self.spread_round_trip_points),
            ("slippage_ticks_per_side", self.slippage_ticks_per_side),
            ("commission_roundtrip_usd", self.commission_roundtrip_usd),
        ):
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError(f"INVALID_COST:{name}")

    @property
    def complete(self) -> bool:
        return all(value is not None for value in (
            self.spread_round_trip_points,
            self.slippage_ticks_per_side,
            self.commission_roundtrip_usd,
        ))

    @property
    def total_roundtrip_points(self) -> float | None:
        if not self.complete:
            return None
        assert self.spread_round_trip_points is not None
        assert self.slippage_ticks_per_side is not None
        assert self.commission_roundtrip_usd is not None
        return (
            self.spread_round_trip_points
            + 2.0 * self.slippage_ticks_per_side * self.tick_size
            + self.commission_roundtrip_usd / self.multiplier_usd_per_point
        )


@dataclass(frozen=True)
class TradeOutcome:
    candidate_id: str
    direction: Literal["LONG", "SHORT"]
    entry_time_utc: datetime
    exit_time_utc: datetime
    entry_reference_price: float
    exit_price_conservative: float
    stop_price: float
    target_price: float
    initial_risk_points: float
    gross_pnl_points_conservative: float
    gross_pnl_usd_per_contract_conservative: float | None
    pnl_r_known: float | None
    pnl_r_conservative: float
    net_pnl_usd_per_contract_conservative: float | None
    net_pnl_r_conservative: float | None
    exit_status: Literal["STOP", "TARGET", "TIME", "AMBIGUOUS"]
    ambiguous_ohlc_order: bool


@dataclass(frozen=True)
class SessionResult:
    session_date: date
    status: Literal["INELIGIBLE", "NO_TRADE", "TRADED"]
    reason: str
    price_range: PriceRange | None
    trade: TradeOutcome | None


@dataclass(frozen=True)
class BacktestSummary:
    variant_id: str
    input_sessions: int
    eligible_sessions: int
    ineligible_sessions: int
    no_trade_sessions: int
    trades: int
    known_order_trades: int
    ambiguous_trades: int
    wins_known: int
    losses_known: int
    win_rate_known: float | None
    average_win_r: float | None
    average_loss_r: float | None
    expectancy_known_r_per_trade: float | None
    profit_factor_known: float | None
    expectancy_conservative_r_per_trade: float | None
    profit_factor_conservative: float | None
    net_expectancy_conservative_r_per_trade: float | None
    net_profit_factor_conservative: float | None
    expectancy_conservative_r_per_eligible_session: float | None
    max_drawdown_conservative_r: float | None
    longest_consecutive_losing_trades: int
    longest_consecutive_losing_sessions: int
    net_economics_status: Literal["CALCULATED", "UNDETERMINED"]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("NAIVE_TIMESTAMP_REJECTED")
    return value.astimezone(timezone.utc)


def _validate_chronological_bars(bars: Sequence[OHLCBar]) -> None:
    if not bars:
        raise ValueError("EMPTY_BAR_SERIES")
    previous: datetime | None = None
    for bar in bars:
        stamp = _utc(bar.timestamp_utc)
        if previous is not None and stamp <= previous:
            raise ValueError("BARS_NOT_STRICTLY_CHRONOLOGICAL")
        values = (bar.open, bar.high, bar.low, bar.close)
        if not all(isfinite(x) and x > 0 for x in values):
            raise ValueError("INVALID_OHLC_PRICE")
        if bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(bar.open, bar.close, bar.high):
            raise ValueError("INVALID_OHLC_RELATIONSHIP")
        previous = stamp


def build_opening_range_15m_from_5m(
    bars_5m: Sequence[OHLCBar],
    session_date: date,
) -> list[OHLCBar]:
    """Aggregate the six NY-open 5m bars into the first two completed 15m bars."""
    _validate_chronological_bars(bars_5m)
    selected = [
        bar for bar in bars_5m
        if (local := _utc(bar.timestamp_utc).astimezone(NEW_YORK)).date() == session_date
        and time(9, 30) <= local.time().replace(tzinfo=None) < time(10, 0)
    ]
    if len(selected) != 6:
        raise ValueError(f"OPENING_30M_INCOMPLETE:expected=6:actual={len(selected)}")
    for i, bar in enumerate(selected):
        local = _utc(bar.timestamp_utc).astimezone(NEW_YORK)
        if local.minute not in {30, 35, 40, 45, 50, 55} or local.second or local.microsecond:
            raise ValueError("OPENING_30M_BAR_NOT_ALIGNED")
        if i and _utc(bar.timestamp_utc) - _utc(selected[i - 1].timestamp_utc) != timedelta(minutes=5):
            raise ValueError("OPENING_30M_GAP_OR_DUPLICATE")

    result: list[OHLCBar] = []
    for offset in (0, 3):
        block = selected[offset:offset + 3]
        result.append(OHLCBar(
            timestamp_utc=_utc(block[0].timestamp_utc),
            open=block[0].open,
            high=max(x.high for x in block),
            low=min(x.low for x in block),
            close=block[-1].close,
        ))
    return result


def _stop_fill(candidate: BreakoutCandidate, bar: OHLCBar) -> float:
    """Use adverse open on a stop gap; otherwise the specified stop level."""
    if candidate.direction == "LONG":
        return min(bar.open, candidate.stop_price)
    return max(bar.open, candidate.stop_price)


def _evaluate_candidate(
    *,
    candidate: BreakoutCandidate,
    bars_5m: Sequence[OHLCBar],
    session_date: date,
    force_flat: time,
    costs: CostModel | None,
) -> SessionResult:
    _validate_chronological_bars(bars_5m)
    by_timestamp = {_utc(bar.timestamp_utc): bar for bar in bars_5m}
    entry_time = _utc(candidate.entry_timestamp_utc)
    if entry_time not in by_timestamp:
        return SessionResult(session_date, "INELIGIBLE", "ENTRY_BAR_MISSING", None, None)

    entry = candidate.entry_reference_price
    risk = candidate.risk_points
    if risk <= 0 or not isfinite(risk):
        return SessionResult(session_date, "NO_TRADE", "INVALID_INITIAL_RISK", None, None)

    expected_flat_open = (datetime.combine(session_date, force_flat) - timedelta(minutes=5)).time()
    flat_bar = None
    for bar in bars_5m:
        local = _utc(bar.timestamp_utc).astimezone(NEW_YORK)
        if local.date() == session_date and local.time().replace(tzinfo=None) == expected_flat_open:
            flat_bar = bar
            break
    if flat_bar is None:
        return SessionResult(session_date, "INELIGIBLE", "FORCE_FLAT_BAR_MISSING", None, None)

    exit_status: Literal["STOP", "TARGET", "TIME", "AMBIGUOUS"] = "TIME"
    exit_price = flat_bar.close
    ambiguous = False
    exit_time = _utc(flat_bar.timestamp_utc) + timedelta(minutes=5)

    for bar in bars_5m:
        stamp = _utc(bar.timestamp_utc)
        if stamp < entry_time:
            continue
        local = stamp.astimezone(NEW_YORK)
        if local.date() != session_date or local.time().replace(tzinfo=None) >= force_flat:
            continue
        if candidate.direction == "LONG":
            stop_hit = bar.low <= candidate.stop_price
            target_hit = bar.high >= candidate.target_price
        else:
            stop_hit = bar.high >= candidate.stop_price
            target_hit = bar.low <= candidate.target_price
        if not stop_hit and not target_hit:
            continue

        exit_time = stamp
        if stop_hit and target_hit:
            exit_status = "AMBIGUOUS"
            exit_price = _stop_fill(candidate, bar)
            ambiguous = True
            break
        if stop_hit:
            exit_status = "STOP"
            exit_price = _stop_fill(candidate, bar)
            break
        exit_status = "TARGET"
        # Limit targets are filled at the target, not improved by a favorable gap.
        exit_price = candidate.target_price
        break

    sign = 1.0 if candidate.direction == "LONG" else -1.0
    gross_points = (exit_price - entry) * sign
    pnl_r_conservative = gross_points / risk
    known_pnl_r = None if ambiguous else pnl_r_conservative
    multiplier = costs.multiplier_usd_per_point if costs else None
    gross_usd = gross_points * multiplier if multiplier is not None else None
    total_cost_points = costs.total_roundtrip_points if costs else None
    net_usd = None
    net_r = None
    if costs is not None and total_cost_points is not None:
        net_points = gross_points - total_cost_points
        net_usd = net_points * costs.multiplier_usd_per_point
        net_r = net_points / risk

    outcome = TradeOutcome(
        candidate_id=candidate.candidate_id,
        direction=candidate.direction,
        entry_time_utc=entry_time,
        exit_time_utc=exit_time,
        entry_reference_price=entry,
        exit_price_conservative=exit_price,
        stop_price=candidate.stop_price,
        target_price=candidate.target_price,
        initial_risk_points=risk,
        gross_pnl_points_conservative=gross_points,
        gross_pnl_usd_per_contract_conservative=gross_usd,
        pnl_r_known=known_pnl_r,
        pnl_r_conservative=pnl_r_conservative,
        net_pnl_usd_per_contract_conservative=net_usd,
        net_pnl_r_conservative=net_r,
        exit_status=exit_status,
        ambiguous_ohlc_order=ambiguous,
    )
    return SessionResult(session_date, "TRADED", "TRADE_EXIT_REPLAYED_FROM_OHLC", None, outcome)


def backtest_session_a(
    bars_5m: Sequence[OHLCBar],
    session_date: date,
    *,
    stop_mode: Literal["OPPOSITE_RANGE_BOUNDARY", "BREAKOUT_CANDLE_EXTREME"],
    target_mode: TargetMode = "R_MULTIPLE",
    target_value: float = 2.0,
    tick_size: float = 0.25,
    costs: CostModel | None = None,
    force_flat: time = SESSION_FLAT_TIME,
) -> SessionResult:
    """Run Candidate A's completed-close variant; intrabar mode is not included."""
    try:
        price_range = premarket_range_5m(bars_5m, session_date)
    except ValueError as exc:
        return SessionResult(session_date, "INELIGIBLE", str(exc), None, None)
    decision = premarket_close_candidate(
        bars_5m, price_range, session_date,
        stop_mode=stop_mode, target_mode=target_mode,
        target_value=target_value, tick_size=tick_size,
    )
    if decision.status == "NO_TRADE":
        return SessionResult(session_date, "NO_TRADE", decision.reason, price_range, None)
    assert decision.candidate is not None
    result = _evaluate_candidate(
        candidate=decision.candidate, bars_5m=bars_5m,
        session_date=session_date, force_flat=force_flat, costs=costs,
    )
    return SessionResult(result.session_date, result.status, result.reason, price_range, result.trade)


def backtest_session_b(
    bars_5m: Sequence[OHLCBar],
    bars_15m: Sequence[OHLCBar],
    session_date: date,
    *,
    target_mode: TargetMode,
    target_value: float,
    costs: CostModel | None = None,
    entry_cutoff: time = time(11, 0),
    force_flat: time = SESSION_FLAT_TIME,
) -> SessionResult:
    """Run Candidate B with a range built from exactly two completed 15m bars."""
    try:
        price_range = opening_range_30m_from_15m(bars_15m, session_date)
    except ValueError as exc:
        return SessionResult(session_date, "INELIGIBLE", str(exc), None, None)
    decision = opening_range_close_candidate(
        bars_5m, price_range, session_date,
        target_mode=target_mode, target_value=target_value,
        entry_cutoff=entry_cutoff,
    )
    if decision.status == "NO_TRADE":
        return SessionResult(session_date, "NO_TRADE", decision.reason, price_range, None)
    assert decision.candidate is not None
    result = _evaluate_candidate(
        candidate=decision.candidate, bars_5m=bars_5m,
        session_date=session_date, force_flat=force_flat, costs=costs,
    )
    return SessionResult(result.session_date, result.status, result.reason, price_range, result.trade)


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _profit_factor(values: Sequence[float]) -> float | None:
    gross_win = sum(x for x in values if x > 0)
    gross_loss = abs(sum(x for x in values if x < 0))
    return None if gross_loss == 0 else gross_win / gross_loss


def _max_drawdown(daily_returns: Sequence[float]) -> float | None:
    if not daily_returns:
        return None
    equity = peak = max_dd = 0.0
    for value in daily_returns:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def summarize_sessions(results: Sequence[SessionResult], *, variant_id: str) -> BacktestSummary:
    ordered_results = sorted(results, key=lambda r: r.session_date)
    input_sessions = len(ordered_results)
    eligible = [r for r in ordered_results if r.status != "INELIGIBLE"]
    no_trade_sessions = sum(1 for r in eligible if r.status == "NO_TRADE")
    trades = [r.trade for r in eligible if r.trade is not None]
    known = [t for t in trades if t.pnl_r_known is not None]
    known_r = [float(t.pnl_r_known) for t in known]
    conservative_r = [t.pnl_r_conservative for t in trades]
    known_wins = [x for x in known_r if x > 0]
    known_losses = [x for x in known_r if x < 0]
    net_complete = bool(trades) and all(t.net_pnl_r_conservative is not None for t in trades)
    net_conservative = [
        float(t.net_pnl_r_conservative) for t in trades
        if t.net_pnl_r_conservative is not None
    ]
    daily_conservative = [
        r.trade.pnl_r_conservative if r.trade is not None else 0.0 for r in eligible
    ]

    # Trade streaks ignore valid NO_TRADE sessions but reset across an ineligible
    # session because missing data cannot be silently bridged.
    trade_streak = longest_trade_streak = 0
    session_streak = longest_session_streak = 0
    for result in ordered_results:
        if result.status == "INELIGIBLE":
            trade_streak = 0
            session_streak = 0
            continue
        if result.trade is None:
            session_streak = 0
            continue
        if result.trade.pnl_r_conservative < 0:
            trade_streak += 1
            session_streak += 1
            longest_trade_streak = max(longest_trade_streak, trade_streak)
            longest_session_streak = max(longest_session_streak, session_streak)
        else:
            trade_streak = 0
            session_streak = 0

    return BacktestSummary(
        variant_id=variant_id,
        input_sessions=input_sessions,
        eligible_sessions=len(eligible),
        ineligible_sessions=input_sessions - len(eligible),
        no_trade_sessions=no_trade_sessions,
        trades=len(trades),
        known_order_trades=len(known),
        ambiguous_trades=sum(1 for t in trades if t.ambiguous_ohlc_order),
        wins_known=len(known_wins),
        losses_known=len(known_losses),
        win_rate_known=len(known_wins) / len(known) if known else None,
        average_win_r=_mean(known_wins),
        average_loss_r=_mean(known_losses),
        expectancy_known_r_per_trade=_mean(known_r),
        profit_factor_known=_profit_factor(known_r),
        expectancy_conservative_r_per_trade=_mean(conservative_r),
        profit_factor_conservative=_profit_factor(conservative_r),
        net_expectancy_conservative_r_per_trade=_mean(net_conservative) if net_complete else None,
        net_profit_factor_conservative=_profit_factor(net_conservative) if net_complete else None,
        expectancy_conservative_r_per_eligible_session=_mean(daily_conservative),
        max_drawdown_conservative_r=_max_drawdown(daily_conservative),
        longest_consecutive_losing_trades=longest_trade_streak,
        longest_consecutive_losing_sessions=longest_session_streak,
        net_economics_status="CALCULATED" if net_complete else "UNDETERMINED",
    )


def grouped_sessions(
    results_by_date: Mapping[date, SessionResult],
    *,
    variant_id: str,
) -> BacktestSummary:
    """Aggregate unique date-keyed session outcomes with no-trade days as zero."""
    return summarize_sessions(list(results_by_date.values()), variant_id=variant_id)
