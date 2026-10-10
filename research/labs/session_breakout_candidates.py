"""Research-only, deterministic primitives for two US-session breakout candidates.

This module constructs candidate signals and reference stop/target prices only.
It is not a backtester, fill simulator, strategy registry, or execution adapter.
All resulting candidates explicitly have no capital or live-order authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import isfinite
from typing import Literal, Sequence
from zoneinfo import ZoneInfo

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False

NEW_YORK = ZoneInfo("America/New_York")
BAR_MINUTES = 5
PREMARKET_RANGE_START = time(4, 0)
PREMARKET_RANGE_END = time(9, 0)
US_CASH_OPEN = time(9, 30)
PREMARKET_ENTRY_CUTOFF = time(11, 0)
OPENING_RANGE_END = time(10, 0)
OPENING_RANGE_ENTRY_CUTOFF = time(11, 0)

StopMode = Literal[
    "OPPOSITE_RANGE_BOUNDARY",
    "BREAKOUT_CANDLE_EXTREME",
    "OBSERVED_EXTREME_AT_SIGNAL",
]
TargetMode = Literal["R_MULTIPLE", "FIXED_POINTS"]


@dataclass(frozen=True)
class OHLCBar:
    """Bar timestamp means bar OPEN time; timestamps must be timezone-aware."""

    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class QuoteTick:
    """One ordered quote/trade observation with stable source sequence metadata."""

    timestamp_utc: datetime
    last: float
    bid: float
    ask: float
    sequence: int


@dataclass(frozen=True)
class PriceRange:
    candidate_id: str
    session_date: date
    high: float
    low: float
    start_utc: datetime
    end_utc: datetime
    bars_count: int


@dataclass(frozen=True)
class BreakoutCandidate:
    candidate_id: str
    direction: Literal["LONG", "SHORT"]
    session_date: date
    signal_timestamp_utc: datetime
    entry_timestamp_utc: datetime
    entry_reference_price: float
    stop_price: float
    target_price: float
    risk_points: float
    stop_mode: str
    target_mode: str
    target_value: float
    price_reference: str
    research_only: bool = True
    capital_authority: bool = False
    live_execution: bool = False


@dataclass(frozen=True)
class ResearchDecision:
    status: Literal["CANDIDATE", "NO_TRADE"]
    reason: str
    candidate: BreakoutCandidate | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("NAIVE_TIMESTAMP_REJECTED")
    return value.astimezone(timezone.utc)


def _finite_price(value: float, label: str) -> float:
    price = float(value)
    if not isfinite(price) or price <= 0:
        raise ValueError(f"INVALID_PRICE:{label}")
    return price


def _validate_bars(bars: Sequence[OHLCBar]) -> None:
    if not bars:
        raise ValueError("EMPTY_BAR_SERIES")
    previous: datetime | None = None
    for bar in bars:
        stamp = _utc(bar.timestamp_utc)
        if previous is not None and stamp <= previous:
            raise ValueError("BARS_NOT_STRICTLY_CHRONOLOGICAL")
        op = _finite_price(bar.open, "open")
        hi = _finite_price(bar.high, "high")
        lo = _finite_price(bar.low, "low")
        cl = _finite_price(bar.close, "close")
        if hi < max(op, cl, lo) or lo > min(op, cl, hi) or hi < lo:
            raise ValueError("INVALID_OHLC_RELATIONSHIP")
        previous = stamp


def _range_bars(
    bars: Sequence[OHLCBar],
    session_date: date,
    start: time,
    end: time,
    interval_minutes: int,
    expected_count: int,
) -> list[OHLCBar]:
    _validate_bars(bars)
    selected = [
        bar for bar in bars
        if (local := _utc(bar.timestamp_utc).astimezone(NEW_YORK)).date() == session_date
        and start <= local.time().replace(tzinfo=None) < end
    ]
    if len(selected) != expected_count:
        raise ValueError(
            f"INCOMPLETE_SESSION_WINDOW:expected={expected_count}:actual={len(selected)}"
        )
    for i, bar in enumerate(selected):
        local = _utc(bar.timestamp_utc).astimezone(NEW_YORK)
        if local.minute % interval_minutes or local.second or local.microsecond:
            raise ValueError("BAR_NOT_ALIGNED_TO_SESSION_GRID")
        if i:
            delta = _utc(bar.timestamp_utc) - _utc(selected[i - 1].timestamp_utc)
            if delta != timedelta(minutes=interval_minutes):
                raise ValueError("SESSION_WINDOW_GAP_OR_DUPLICATE")
    return selected


def premarket_range_5m(bars: Sequence[OHLCBar], session_date: date) -> PriceRange:
    """Build [04:00, 09:00) America/New_York range from exactly 60 5m bars."""
    selected = _range_bars(
        bars, session_date, PREMARKET_RANGE_START, PREMARKET_RANGE_END, 5, 60
    )
    start = datetime.combine(session_date, PREMARKET_RANGE_START, NEW_YORK)
    end = datetime.combine(session_date, PREMARKET_RANGE_END, NEW_YORK)
    range_high = max(bar.high for bar in selected)
    range_low = min(bar.low for bar in selected)
    if range_high <= range_low:
        raise ValueError("DEGENERATE_SESSION_RANGE")
    return PriceRange(
        candidate_id="US_PREMARKET_RANGE_BREAKOUT",
        session_date=session_date,
        high=range_high,
        low=range_low,
        start_utc=start.astimezone(timezone.utc),
        end_utc=end.astimezone(timezone.utc),
        bars_count=len(selected),
    )


def opening_range_30m_from_15m(
    bars: Sequence[OHLCBar], session_date: date
) -> PriceRange:
    """Build the 09:30-10:00 range from the two 15m bars starting 09:30/09:45."""
    selected = _range_bars(
        bars, session_date, US_CASH_OPEN, OPENING_RANGE_END, 15, 2
    )
    start = datetime.combine(session_date, US_CASH_OPEN, NEW_YORK)
    end = datetime.combine(session_date, OPENING_RANGE_END, NEW_YORK)
    range_high = max(bar.high for bar in selected)
    range_low = min(bar.low for bar in selected)
    if range_high <= range_low:
        raise ValueError("DEGENERATE_SESSION_RANGE")
    return PriceRange(
        candidate_id="US_OPENING_RANGE_30M_BREAKOUT",
        session_date=session_date,
        high=range_high,
        low=range_low,
        start_utc=start.astimezone(timezone.utc),
        end_utc=end.astimezone(timezone.utc),
        bars_count=len(selected),
    )


def _make_candidate(
    *,
    candidate_id: str,
    direction: Literal["LONG", "SHORT"],
    session_date: date,
    signal_time_utc: datetime,
    entry_time_utc: datetime,
    entry_price: float,
    stop_price: float,
    target_mode: TargetMode,
    target_value: float,
    stop_mode: str,
    price_reference: str,
) -> ResearchDecision:
    entry = _finite_price(entry_price, "entry_reference")
    stop = _finite_price(stop_price, "stop")
    if direction == "LONG":
        risk = entry - stop
    else:
        risk = stop - entry
    if not isfinite(risk) or risk <= 0:
        return ResearchDecision("NO_TRADE", "ENTRY_GAP_INVALIDATES_STOP")
    if not isfinite(target_value) or target_value <= 0:
        raise ValueError("TARGET_VALUE_MUST_BE_POSITIVE")
    if target_mode == "R_MULTIPLE":
        target_distance = risk * target_value
    elif target_mode == "FIXED_POINTS":
        target_distance = target_value
    else:
        raise ValueError("UNSUPPORTED_TARGET_MODE")
    target = entry + target_distance if direction == "LONG" else entry - target_distance
    candidate = BreakoutCandidate(
        candidate_id=candidate_id,
        direction=direction,
        session_date=session_date,
        signal_timestamp_utc=_utc(signal_time_utc),
        entry_timestamp_utc=_utc(entry_time_utc),
        entry_reference_price=entry,
        stop_price=stop,
        target_price=target,
        risk_points=risk,
        stop_mode=stop_mode,
        target_mode=target_mode,
        target_value=float(target_value),
        price_reference=price_reference,
    )
    return ResearchDecision("CANDIDATE", "FIRST_ELIGIBLE_BREAKOUT", candidate)


def _close_breakout_candidate(
    *,
    candidate_id: str,
    bars_5m: Sequence[OHLCBar],
    price_range: PriceRange,
    session_date: date,
    signal_start: time,
    cutoff: time,
    stop_mode: StopMode,
    target_mode: TargetMode,
    target_value: float,
    tick_size: float,
    opposite_boundary_only: bool = False,
) -> ResearchDecision:
    _validate_bars(bars_5m)
    if (
        price_range.session_date != session_date
        or not isfinite(price_range.high)
        or not isfinite(price_range.low)
        or price_range.high <= price_range.low
    ):
        raise ValueError("RANGE_SESSION_OR_PRICE_INVALID")
    if cutoff <= signal_start:
        raise ValueError("ENTRY_CUTOFF_MUST_FOLLOW_SIGNAL_START")
    # A batch result must include every five-minute bar in the candidate window.
    # Otherwise an earlier breakout may be missing and the first-signal rule cannot be trusted.
    window_bars = [
        bar for bar in bars_5m
        if (local := _utc(bar.timestamp_utc).astimezone(NEW_YORK)).date() == session_date
        and signal_start <= local.time().replace(tzinfo=None) < cutoff
    ]
    expected_window_bars = int(
        (datetime.combine(session_date, cutoff) - datetime.combine(session_date, signal_start))
        .total_seconds() // (BAR_MINUTES * 60)
    )
    if expected_window_bars <= 0 or len(window_bars) != expected_window_bars:
        return ResearchDecision("NO_TRADE", "ENTRY_WINDOW_INCOMPLETE")
    for i, bar in enumerate(window_bars):
        local = _utc(bar.timestamp_utc).astimezone(NEW_YORK)
        if local.minute % BAR_MINUTES or local.second or local.microsecond:
            return ResearchDecision("NO_TRADE", "ENTRY_WINDOW_UNALIGNED")
        if i and _utc(bar.timestamp_utc) - _utc(window_bars[i - 1].timestamp_utc) != timedelta(minutes=BAR_MINUTES):
            return ResearchDecision("NO_TRADE", "ENTRY_WINDOW_GAP")
    if not isfinite(tick_size) or tick_size <= 0:
        raise ValueError("TICK_SIZE_MUST_BE_POSITIVE")
    if stop_mode == "OBSERVED_EXTREME_AT_SIGNAL":
        raise ValueError("OBSERVED_EXTREME_STOP_REQUIRES_INTRABAR_TICK_MODE")
    if opposite_boundary_only and stop_mode != "OPPOSITE_RANGE_BOUNDARY":
        raise ValueError("OPENING_RANGE_STOP_MUST_BE_OPPOSITE_BOUNDARY")

    by_start = {_utc(bar.timestamp_utc): bar for bar in bars_5m}
    for bar in bars_5m:
        local = _utc(bar.timestamp_utc).astimezone(NEW_YORK)
        close_utc = _utc(bar.timestamp_utc) + timedelta(minutes=BAR_MINUTES)
        local_close = close_utc.astimezone(NEW_YORK)
        if local.date() != session_date or local.time().replace(tzinfo=None) < signal_start:
            continue
        # The next-bar reference entry must be strictly before the cutoff.
        if local_close.date() != session_date or local_close.time().replace(tzinfo=None) >= cutoff:
            continue
        direction: Literal["LONG", "SHORT"] | None = (
            "LONG" if bar.close > price_range.high
            else "SHORT" if bar.close < price_range.low
            else None
        )
        if direction is None:
            continue
        entry_bar = by_start.get(close_utc)
        if entry_bar is None:
            return ResearchDecision("NO_TRADE", "NEXT_BAR_MISSING_AT_SIGNAL_CLOSE")
        entry_local = _utc(entry_bar.timestamp_utc).astimezone(NEW_YORK)
        if entry_local.date() != session_date or entry_local.time().replace(tzinfo=None) >= cutoff:
            return ResearchDecision("NO_TRADE", "NEXT_EXECUTABLE_BAR_OUTSIDE_ENTRY_WINDOW")

        if stop_mode == "OPPOSITE_RANGE_BOUNDARY":
            stop = price_range.low if direction == "LONG" else price_range.high
        elif stop_mode == "BREAKOUT_CANDLE_EXTREME":
            stop = bar.low - tick_size if direction == "LONG" else bar.high + tick_size
        else:
            raise ValueError("UNSUPPORTED_STOP_MODE")
        return _make_candidate(
            candidate_id=candidate_id,
            direction=direction,
            session_date=session_date,
            signal_time_utc=close_utc,
            entry_time_utc=entry_bar.timestamp_utc,
            entry_price=entry_bar.open,
            stop_price=stop,
            target_mode=target_mode,
            target_value=target_value,
            stop_mode=stop_mode,
            price_reference="NEXT_5M_BAR_OPEN_PROXY_NOT_AN_EXECUTION_FILL",
        )
    return ResearchDecision("NO_TRADE", "NO_BREAKOUT")


def premarket_close_candidate(
    bars_5m: Sequence[OHLCBar],
    price_range: PriceRange,
    session_date: date,
    *,
    stop_mode: Literal["OPPOSITE_RANGE_BOUNDARY", "BREAKOUT_CANDLE_EXTREME"],
    target_mode: TargetMode = "R_MULTIPLE",
    target_value: float = 2.0,
    tick_size: float = 0.25,
) -> ResearchDecision:
    """First 5m CLOSE outside range, after which next-bar open is a proxy only."""
    return _close_breakout_candidate(
        candidate_id="US_PREMARKET_RANGE_BREAKOUT_CLOSE_V1",
        bars_5m=bars_5m,
        price_range=price_range,
        session_date=session_date,
        signal_start=US_CASH_OPEN,
        cutoff=PREMARKET_ENTRY_CUTOFF,
        stop_mode=stop_mode,
        target_mode=target_mode,
        target_value=target_value,
        tick_size=tick_size,
    )


def opening_range_close_candidate(
    bars_5m: Sequence[OHLCBar],
    price_range: PriceRange,
    session_date: date,
    *,
    target_mode: TargetMode,
    target_value: float,
    entry_cutoff: time = OPENING_RANGE_ENTRY_CUTOFF,
) -> ResearchDecision:
    """First 5m CLOSE outside 09:30-10:00 range; opposite-boundary stop only."""
    return _close_breakout_candidate(
        candidate_id="US_OPENING_RANGE_30M_BREAKOUT_CLOSE_V1",
        bars_5m=bars_5m,
        price_range=price_range,
        session_date=session_date,
        signal_start=OPENING_RANGE_END,
        cutoff=entry_cutoff,
        stop_mode="OPPOSITE_RANGE_BOUNDARY",
        target_mode=target_mode,
        target_value=target_value,
        tick_size=0.25,
        opposite_boundary_only=True,
    )


def premarket_intrabar_candidate(
    ticks: Sequence[QuoteTick],
    price_range: PriceRange,
    session_date: date,
    *,
    stop_mode: Literal["OPPOSITE_RANGE_BOUNDARY", "OBSERVED_EXTREME_AT_SIGNAL"],
    target_value_r: float = 2.0,
    tick_size: float = 0.25,
    entry_cutoff: time = PREMARKET_ENTRY_CUTOFF,
) -> ResearchDecision:
    """First tick breakout; requires ordered tick+bid/ask data and a later quote.

    The full final high/low of the breakout candle is forbidden as an intrabar
    stop because those future prices were not yet known at the signal timestamp.
    """
    if stop_mode == "BREAKOUT_CANDLE_EXTREME":
        raise ValueError("INTRABAR_FINAL_CANDLE_EXTREME_WOULD_LOOK_AHEAD")
    if stop_mode not in {"OPPOSITE_RANGE_BOUNDARY", "OBSERVED_EXTREME_AT_SIGNAL"}:
        raise ValueError("UNSUPPORTED_INTRABAR_STOP_MODE")
    if not isfinite(tick_size) or tick_size <= 0:
        raise ValueError("TICK_SIZE_MUST_BE_POSITIVE")
    if not isfinite(target_value_r) or target_value_r <= 0:
        raise ValueError("TARGET_R_MUST_BE_POSITIVE")
    if not ticks:
        return ResearchDecision("NO_TRADE", "NO_TICK_DATA")

    previous_key: tuple[datetime, int] | None = None
    selected: list[QuoteTick] = []
    if (
        price_range.session_date != session_date
        or not isfinite(price_range.high)
        or not isfinite(price_range.low)
        or price_range.high <= price_range.low
    ):
        raise ValueError("RANGE_SESSION_OR_PRICE_INVALID")
    for tick in ticks:
        stamp = _utc(tick.timestamp_utc)
        key = (stamp, tick.sequence)
        if tick.sequence < 0 or (previous_key is not None and key <= previous_key):
            raise ValueError("TICKS_NOT_STRICTLY_ORDERED_BY_TIMESTAMP_AND_SEQUENCE")
        last = _finite_price(tick.last, "last")
        bid = _finite_price(tick.bid, "bid")
        ask = _finite_price(tick.ask, "ask")
        if bid > ask:
            raise ValueError("CROSSED_QUOTE")
        previous_key = key
        local = stamp.astimezone(NEW_YORK)
        if local.date() == session_date and US_CASH_OPEN <= local.time().replace(tzinfo=None) < entry_cutoff:
            selected.append(QuoteTick(stamp, last, bid, ask, tick.sequence))

    if len(selected) < 2:
        return ResearchDecision("NO_TRADE", "INSUFFICIENT_POST_SIGNAL_QUOTES")

    observed_high: float | None = None
    observed_low: float | None = None
    bar_key: tuple[int, int, int, int, int] | None = None
    for i, tick in enumerate(selected):
        local = tick.timestamp_utc.astimezone(NEW_YORK)
        key = (local.year, local.month, local.day, local.hour, local.minute // BAR_MINUTES)
        if key != bar_key:
            bar_key = key
            observed_high = tick.last
            observed_low = tick.last
        else:
            observed_high = max(float(observed_high), tick.last)
            observed_low = min(float(observed_low), tick.last)

        direction: Literal["LONG", "SHORT"] | None = (
            "LONG" if tick.last > price_range.high
            else "SHORT" if tick.last < price_range.low
            else None
        )
        if direction is None:
            continue
        if i + 1 >= len(selected):
            return ResearchDecision("NO_TRADE", "NO_POST_SIGNAL_EXECUTABLE_QUOTE")
        next_tick = selected[i + 1]
        # Candidates store timestamps but not sub-second event IDs; equal timestamps
        # therefore cannot prove post-signal ordering in the resulting evidence.
        if next_tick.timestamp_utc <= tick.timestamp_utc:
            return ResearchDecision("NO_TRADE", "SAME_TIMESTAMP_QUOTE_ORDER_AMBIGUOUS")
        entry = next_tick.ask if direction == "LONG" else next_tick.bid
        if stop_mode == "OPPOSITE_RANGE_BOUNDARY":
            stop = price_range.low if direction == "LONG" else price_range.high
        else:
            assert observed_low is not None and observed_high is not None
            stop = (
                observed_low - tick_size if direction == "LONG"
                else observed_high + tick_size
            )
        return _make_candidate(
            candidate_id="US_PREMARKET_RANGE_BREAKOUT_INTRABAR_V1",
            direction=direction,
            session_date=session_date,
            signal_time_utc=tick.timestamp_utc,
            entry_time_utc=next_tick.timestamp_utc,
            entry_price=entry,
            stop_price=stop,
            target_mode="R_MULTIPLE",
            target_value=target_value_r,
            stop_mode=stop_mode,
            price_reference="NEXT_TICK_ASK_FOR_LONG_BID_FOR_SHORT",
        )
    return ResearchDecision("NO_TRADE", "NO_BREAKOUT")
