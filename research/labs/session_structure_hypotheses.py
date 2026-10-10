"""Research-only primitives for session sweep/reversal and multi-timeframe structure.

This module emits observations and descriptive context only. It does not backtest
trade exits, infer a tradable edge, or grant execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import isfinite
from typing import Literal, Mapping, Sequence
from zoneinfo import ZoneInfo

from research.labs.session_breakout_candidates import OHLCBar

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False

NEW_YORK = ZoneInfo("America/New_York")
SessionName = Literal["OVERNIGHT", "EUROPE", "US_DAY"]
Bias = Literal["BULLISH", "BEARISH", "MIXED", "UNKNOWN"]
SignalDirection = Literal["LONG", "SHORT"]


@dataclass(frozen=True)
class SessionKey:
    session_date: date
    name: SessionName


@dataclass(frozen=True)
class SessionSummary:
    key: SessionKey
    start_utc: datetime
    end_utc: datetime
    high: float
    low: float
    bar_count: int
    complete_grid: bool


@dataclass(frozen=True)
class SessionReversalSignal:
    key: SessionKey
    direction: SignalDirection
    signal_bar_open_utc: datetime
    signal_available_at_utc: datetime
    signal_price: float
    prior_session_high: float
    prior_session_low: float
    stop_reference_price: float
    ambiguity: bool = False
    research_only: bool = True
    capital_authority: bool = False
    live_execution: bool = False


@dataclass(frozen=True)
class SessionExpansionObservation:
    signal_key: SessionKey
    following_key: SessionKey
    directional_signal: SignalDirection
    prior_20_same_type_median_range: float | None
    following_session_range: float
    expansion_ratio: float | None
    research_only: bool = True
    capital_authority: bool = False
    live_execution: bool = False


@dataclass(frozen=True)
class ConfirmedPivot:
    kind: Literal["HIGH", "LOW"]
    pivot_bar_open_utc: datetime
    confirmation_available_at_utc: datetime
    price: float


@dataclass(frozen=True)
class StructureState:
    timeframe: str
    asof_utc: datetime
    bias: Bias
    confirmed_highs: tuple[ConfirmedPivot, ...]
    confirmed_lows: tuple[ConfirmedPivot, ...]
    pivots_seen: int


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("NAIVE_TIMESTAMP_REJECTED")
    return value.astimezone(timezone.utc)


def _validate_bars(bars: Sequence[OHLCBar]) -> None:
    if not bars:
        raise ValueError("EMPTY_BAR_SERIES")
    previous: datetime | None = None
    for bar in bars:
        stamp = _utc(bar.timestamp_utc)
        if previous is not None and stamp <= previous:
            raise ValueError("BARS_NOT_STRICTLY_CHRONOLOGICAL")
        vals = (bar.open, bar.high, bar.low, bar.close)
        if not all(isfinite(v) and v > 0 for v in vals):
            raise ValueError("INVALID_OHLC_PRICE")
        if bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(bar.open, bar.close, bar.high):
            raise ValueError("INVALID_OHLC_RELATIONSHIP")
        previous = stamp


def classify_new_york_session(timestamp: datetime) -> SessionKey | None:
    """Return a trading date/session name; 17:00-18:00 ET is outside sessions.

    OVERNIGHT for trading date D is [18:00 on D-1, 02:00 on D).
    EUROPE is [02:00, 09:30) ET. US_DAY is [09:30, 17:00) ET.
    """
    local = _utc(timestamp).astimezone(NEW_YORK)
    t = local.time().replace(tzinfo=None)
    if t >= time(18, 0):
        return SessionKey(local.date() + timedelta(days=1), "OVERNIGHT")
    if t < time(2, 0):
        return SessionKey(local.date(), "OVERNIGHT")
    if time(2, 0) <= t < time(9, 30):
        return SessionKey(local.date(), "EUROPE")
    if time(9, 30) <= t < time(17, 0):
        return SessionKey(local.date(), "US_DAY")
    return None


def build_session_summaries(
    bars: Sequence[OHLCBar],
    *,
    expected_interval: timedelta = timedelta(minutes=5),
) -> list[SessionSummary]:
    """Aggregate eligible bars; report missing-grid sessions instead of filling gaps."""
    _validate_bars(bars)
    if expected_interval <= timedelta(0):
        raise ValueError("EXPECTED_INTERVAL_MUST_BE_POSITIVE")
    groups: dict[SessionKey, list[OHLCBar]] = {}
    for bar in bars:
        key = classify_new_york_session(bar.timestamp_utc)
        if key is not None:
            groups.setdefault(key, []).append(bar)

    ordered_groups = sorted(
        groups.items(),
        key=lambda pair: _utc(pair[1][0].timestamp_utc),
    )
    summaries: list[SessionSummary] = []
    for key, rows in ordered_groups:
        rows = sorted(rows, key=lambda item: _utc(item.timestamp_utc))
        deltas = [
            _utc(rows[i].timestamp_utc) - _utc(rows[i - 1].timestamp_utc)
            for i in range(1, len(rows))
        ]
        complete = all(delta == expected_interval for delta in deltas)
        summaries.append(SessionSummary(
            key=key,
            start_utc=_utc(rows[0].timestamp_utc),
            end_utc=_utc(rows[-1].timestamp_utc) + expected_interval,
            high=max(x.high for x in rows),
            low=min(x.low for x in rows),
            bar_count=len(rows),
            complete_grid=complete,
        ))
    return summaries


def detect_session_reversal(
    current_bars: Sequence[OHLCBar],
    current_key: SessionKey,
    previous_session: SessionSummary,
    *,
    tick_size: float,
    expected_interval: timedelta = timedelta(minutes=5),
) -> SessionReversalSignal | None:
    """Return first prior-session sweep/re-entry signal, using completed bars.

    A previous high sweep requires high > prior high + no extra buffer (one
    strict instrument tick beyond the prior boundary) and close < prior high.
    A previous low sweep mirrors the rule. If both boundaries are swept by the
    same candle, return an explicit ambiguous observation instead of direction.
    The stop uses the full current-session extreme, which is known only after the
    signal session has closed; this is suitable for the proposed next-session
    entry hypothesis, not an intrabar entry.
    """
    _validate_bars(current_bars)
    if tick_size <= 0 or not isfinite(tick_size):
        raise ValueError("TICK_SIZE_MUST_BE_POSITIVE")
    if not current_bars:
        return None

    local_rows = [
        bar for bar in current_bars
        if classify_new_york_session(bar.timestamp_utc) == current_key
    ]
    if not local_rows:
        return None
    local_rows.sort(key=lambda item: _utc(item.timestamp_utc))
    for index, bar in enumerate(local_rows):
        stamp = _utc(bar.timestamp_utc)
        close_at = stamp + expected_interval
        long_sweep = bar.low <= previous_session.low - tick_size and bar.close > previous_session.low
        short_sweep = bar.high >= previous_session.high + tick_size and bar.close < previous_session.high
        if not long_sweep and not short_sweep:
            continue
        if long_sweep and short_sweep:
            direction: SignalDirection = "LONG"
            stop = min(x.low for x in local_rows) - tick_size
            return SessionReversalSignal(
                key=current_key,
                direction=direction,
                signal_bar_open_utc=stamp,
                signal_available_at_utc=close_at,
                signal_price=bar.close,
                prior_session_high=previous_session.high,
                prior_session_low=previous_session.low,
                stop_reference_price=stop,
                ambiguity=True,
            )
        if long_sweep:
            direction = "LONG"
            stop = min(x.low for x in local_rows) - tick_size
        else:
            direction = "SHORT"
            stop = max(x.high for x in local_rows) + tick_size
        return SessionReversalSignal(
            key=current_key,
            direction=direction,
            signal_bar_open_utc=stamp,
            signal_available_at_utc=close_at,
            signal_price=bar.close,
            prior_session_high=previous_session.high,
            prior_session_low=previous_session.low,
            stop_reference_price=stop,
        )
    return None


def session_expansion_observation(
    signal: SessionReversalSignal,
    following: SessionSummary,
    prior_same_type_ranges: Sequence[float],
) -> SessionExpansionObservation:
    """Describe following-session range expansion vs prior same-type median."""
    if following.key == signal.key:
        raise ValueError("FOLLOWING_SESSION_MUST_DIFFER")
    if any(not isfinite(x) or x < 0 for x in prior_same_type_ranges):
        raise ValueError("INVALID_PRIOR_SESSION_RANGE")
    ranges = sorted(prior_same_type_ranges)
    n = len(ranges)
    median = None
    if n:
        median = ranges[n // 2] if n % 2 else (ranges[n // 2 - 1] + ranges[n // 2]) / 2
    next_range = following.high - following.low
    ratio = next_range / median if median is not None and median > 0 else None
    return SessionExpansionObservation(
        signal_key=signal.key,
        following_key=following.key,
        directional_signal=signal.direction,
        prior_20_same_type_median_range=median,
        following_session_range=next_range,
        expansion_ratio=ratio,
    )


def confirmed_pivots(
    bars: Sequence[OHLCBar],
    *,
    timeframe: timedelta,
    left_bars: int = 2,
    right_bars: int = 2,
) -> list[ConfirmedPivot]:
    """Strict swing points confirmed only after all right-side bars have closed."""
    _validate_bars(bars)
    if timeframe <= timedelta(0) or left_bars < 1 or right_bars < 1:
        raise ValueError("INVALID_PIVOT_CONFIGURATION")
    result: list[ConfirmedPivot] = []
    for i in range(left_bars, len(bars) - right_bars):
        bar = bars[i]
        before = bars[i - left_bars:i]
        after = bars[i + 1:i + right_bars + 1]
        is_high = all(bar.high > other.high for other in (*before, *after))
        is_low = all(bar.low < other.low for other in (*before, *after))
        confirmation_bar = after[-1]
        available_at = _utc(confirmation_bar.timestamp_utc) + timeframe
        if is_high:
            result.append(ConfirmedPivot(
                "HIGH", _utc(bar.timestamp_utc), available_at, bar.high
            ))
        if is_low:
            result.append(ConfirmedPivot(
                "LOW", _utc(bar.timestamp_utc), available_at, bar.low
            ))
    return sorted(result, key=lambda p: (p.confirmation_available_at_utc, p.pivot_bar_open_utc, p.kind))


def _directional_pair(rows: Sequence[ConfirmedPivot], kind: str) -> Bias:
    same_kind = [x for x in rows if x.kind == kind]
    if len(same_kind) < 2:
        return "UNKNOWN"
    old, new = same_kind[-2], same_kind[-1]
    if kind == "HIGH":
        return "BULLISH" if new.price > old.price else "BEARISH" if new.price < old.price else "MIXED"
    return "BULLISH" if new.price > old.price else "BEARISH" if new.price < old.price else "MIXED"


def structure_asof(
    bars: Sequence[OHLCBar],
    *,
    timeframe: timedelta,
    timeframe_label: str,
    decision_timestamp: datetime,
    max_pivots: int = 50,
) -> StructureState:
    """Calculate structure from pivots whose right-side confirmation is known as-of."""
    decision = _utc(decision_timestamp)
    all_pivots = confirmed_pivots(bars, timeframe=timeframe)
    visible = [p for p in all_pivots if p.confirmation_available_at_utc <= decision]
    highs = tuple(p for p in visible if p.kind == "HIGH")[-max_pivots:]
    lows = tuple(p for p in visible if p.kind == "LOW")[-max_pivots:]
    high_bias = _directional_pair(highs, "HIGH")
    low_bias = _directional_pair(lows, "LOW")
    bias: Bias
    if high_bias == low_bias and high_bias in {"BULLISH", "BEARISH"}:
        bias = high_bias
    elif high_bias == "UNKNOWN" or low_bias == "UNKNOWN":
        bias = "UNKNOWN"
    else:
        bias = "MIXED"
    return StructureState(
        timeframe=timeframe_label,
        asof_utc=decision,
        bias=bias,
        confirmed_highs=highs,
        confirmed_lows=lows,
        pivots_seen=len(visible),
    )


def multi_timeframe_context(
    bars_by_timeframe: Mapping[str, Sequence[OHLCBar]],
    intervals: Mapping[str, timedelta],
    *,
    decision_timestamp: datetime,
) -> dict[str, StructureState]:
    """Return one causal state per requested timeframe; missing inputs are UNKNOWN."""
    decision = _utc(decision_timestamp)
    result: dict[str, StructureState] = {}
    for label, interval in intervals.items():
        rows = bars_by_timeframe.get(label, ())
        if not rows:
            result[label] = StructureState(label, decision, "UNKNOWN", (), (), 0)
            continue
        result[label] = structure_asof(
            rows,
            timeframe=interval,
            timeframe_label=label,
            decision_timestamp=decision,
        )
    return result


def directional_alignment(
    states: Mapping[str, StructureState],
    expected: SignalDirection,
) -> Literal["PASS", "FAIL", "UNKNOWN"]:
    """Optional research filter; unknown timeframes do not silently pass."""
    if not states:
        return "UNKNOWN"
    target: Bias = "BULLISH" if expected == "LONG" else "BEARISH"
    biases = [state.bias for state in states.values()]
    if any(bias == "UNKNOWN" for bias in biases):
        return "UNKNOWN"
    return "PASS" if all(bias == target for bias in biases) else "FAIL"
