"""Research-only liquidity sweep strategy; no broker or capital authority.

Signals are emitted only when a completed confirmation candle exists and a
subsequent bar is available for a conservative next-bar-open entry simulation.
This module is deliberately independent of runtime execution components.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from typing import Iterable, Mapping, Sequence

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False


@dataclass(frozen=True)
class OHLCBar:
    timestamp_utc: str
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class ResearchSignal:
    direction: str
    sweep_index: int
    reclaim_index: int
    confirmation_index: int
    entry_index: int
    entry_price: float
    stop_price: float
    target_price: float
    swept_level: float
    reward_risk: float


def _parse_bar(item: OHLCBar | Mapping[str, object]) -> OHLCBar:
    if isinstance(item, OHLCBar):
        bar = item
    else:
        try:
            bar = OHLCBar(
                timestamp_utc=str(item["timestamp_utc"]),
                open=float(item["open"]), high=float(item["high"]),
                low=float(item["low"]), close=float(item["close"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("each bar requires timestamp_utc, open, high, low, close") from exc
    try:
        dt = datetime.fromisoformat(bar.timestamp_utc.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp_utc") from exc
    if dt.tzinfo is None:
        raise ValueError("timestamp_utc must be timezone-aware")
    values = (bar.open, bar.high, bar.low, bar.close)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("OHLC values must be finite")
    if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close) or bar.low > bar.high:
        raise ValueError("invalid OHLC range")
    return bar


def _confirmed_pivot(bars: Sequence[OHLCBar], pivot_index: int, window: int, kind: str) -> bool:
    left = bars[pivot_index - window:pivot_index]
    right = bars[pivot_index + 1:pivot_index + window + 1]
    if len(left) != window or len(right) != window:
        return False
    if kind == "high":
        return all(bars[pivot_index].high > b.high for b in (*left, *right))
    return all(bars[pivot_index].low < b.low for b in (*left, *right))





def resample_1m_to_15m(
    raw_bars: Iterable[OHLCBar | Mapping[str, object]],
) -> list[OHLCBar]:
    """Aggregate complete 1m close-timestamp bars into 15m OHLC bars.

    Only exact, gap-free buckets of fifteen unique 1m candles are emitted.
    A label is the 15m candle close time. No volume field is inferred or used,
    which is intentional for Deriv synthetic indices.
    """
    bars = [_parse_bar(item) for item in raw_bars]
    times = [datetime.fromisoformat(b.timestamp_utc.replace("Z", "+00:00")) for b in bars]
    if any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError("bar timestamps must be strictly increasing")

    buckets: dict[datetime, list[tuple[datetime, OHLCBar]]] = {}
    for stamp, bar in zip(times, bars):
        if stamp.second != 0 or stamp.microsecond != 0:
            raise ValueError("1m candle-close timestamps must align to whole minutes")
        midnight = stamp.replace(hour=0, minute=0, second=0, microsecond=0)
        minute_of_day = stamp.hour * 60 + stamp.minute
        end_minute = ((minute_of_day + 14) // 15) * 15
        bucket_end = midnight + timedelta(minutes=end_minute)
        buckets.setdefault(bucket_end, []).append((stamp, bar))

    completed: list[OHLCBar] = []
    one_minute = timedelta(minutes=1)
    for bucket_end in sorted(buckets):
        values = sorted(buckets[bucket_end], key=lambda item: item[0])
        required = [bucket_end - one_minute * offset for offset in range(14, -1, -1)]
        actual_times = [stamp for stamp, _ in values]
        if actual_times != required:
            # A partial or gappy 15m window is not a completed context candle.
            continue
        candle_values = [bar for _, bar in values]
        label = bucket_end.isoformat().replace("+00:00", "Z")
        completed.append(OHLCBar(
            timestamp_utc=label,
            open=candle_values[0].open,
            high=max(bar.high for bar in candle_values),
            low=min(bar.low for bar in candle_values),
            close=candle_values[-1].close,
        ))
    return completed


def _context_direction(
    raw_context_bars: Sequence[OHLCBar],
    before_time: datetime,
    pivot_window: int,
) -> str | None:
    """Return a strict 15m market-structure bias using bars closed before signal time.

    Bias is bullish only when the latest two confirmed 15m swing highs and
    swing lows are both rising; bearish only when both are falling. Otherwise
    the context is neutral and a candidate is rejected.
    """
    available: list[OHLCBar] = []
    for bar in raw_context_bars:
        stamp = datetime.fromisoformat(bar.timestamp_utc.replace("Z", "+00:00"))
        if stamp < before_time:
            available.append(bar)
        else:
            break
    if len(available) < 2 * pivot_window + 1:
        return None

    context_highs: list[float] = []
    context_lows: list[float] = []
    for idx in range(pivot_window, len(available) - pivot_window):
        if _confirmed_pivot(available, idx, pivot_window, "high"):
            context_highs.append(available[idx].high)
        if _confirmed_pivot(available, idx, pivot_window, "low"):
            context_lows.append(available[idx].low)
    if len(context_highs) < 2 or len(context_lows) < 2:
        return None
    high_rising = context_highs[-1] > context_highs[-2]
    low_rising = context_lows[-1] > context_lows[-2]
    high_falling = context_highs[-1] < context_highs[-2]
    low_falling = context_lows[-1] < context_lows[-2]
    if high_rising and low_rising:
        return "long"
    if high_falling and low_falling:
        return "short"
    return None


def generate_research_signals(
    raw_bars: Iterable[OHLCBar | Mapping[str, object]],
    *,
    context_bars_15m: Iterable[OHLCBar | Mapping[str, object]] | None = None,
    pivot_window: int = 2,
    reclaim_window: int = 3,
    reward_risk: float = 2.0,
    stop_buffer: float = 0.0,
) -> list[ResearchSignal]:
    """Generate long/short research candidates from completed OHLC bars.

    Pivots are usable only after their right-side confirmation bars complete.
    Each candidate must agree with a directional 15m structure bias computed
    only from context candles whose timestamps are strictly earlier than the
    1m confirmation candle. Neutral or insufficient context rejects the signal.
    Confirmation is followed by entry at the next bar's open. Signals are
    research records only; costs, stake sizing, probability gates and execution
    authorization must be handled separately by existing AURELIA controls.

    Timestamps on both series represent candle-close times in ISO-8601 UTC (or
    another explicit timezone). Input series must be strictly chronological.
    """
    if isinstance(pivot_window, bool) or not isinstance(pivot_window, int) or pivot_window < 1:
        raise ValueError("pivot_window must be a positive integer")
    if isinstance(reclaim_window, bool) or not isinstance(reclaim_window, int) or reclaim_window < 1:
        raise ValueError("reclaim_window must be a positive integer")
    if not math.isfinite(reward_risk) or reward_risk not in (2.0, 3.0):
        raise ValueError("reward_risk must be preregistered as 2.0 or 3.0")
    if not math.isfinite(stop_buffer) or stop_buffer < 0:
        raise ValueError("stop_buffer must be finite and non-negative")

    bars = [_parse_bar(x) for x in raw_bars]
    parsed_times = [datetime.fromisoformat(b.timestamp_utc.replace("Z", "+00:00")) for b in bars]
    if any(a >= b for a, b in zip(parsed_times, parsed_times[1:])):
        raise ValueError("bar timestamps must be strictly increasing")
    if len(bars) < 2 * pivot_window + 3:
        return []
    if context_bars_15m is None:
        raise ValueError("completed context_bars_15m are required; missing context fails closed")
    context_bars = [_parse_bar(x) for x in context_bars_15m]
    context_times = [datetime.fromisoformat(b.timestamp_utc.replace("Z", "+00:00")) for b in context_bars]
    if any(a >= b for a, b in zip(context_times, context_times[1:])):
        raise ValueError("15m context timestamps must be strictly increasing")

    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    pending: dict[str, dict[str, float | int]] = {}
    signals: list[ResearchSignal] = []
    # i is the currently completed candle. A pivot at i-window only becomes
    # knowable now, after all required right-side bars have closed.
    for i in range(pivot_window * 2, len(bars) - 1):
        candidate_pivot = i - pivot_window
        if _confirmed_pivot(bars, candidate_pivot, pivot_window, "high"):
            highs.append((candidate_pivot, bars[candidate_pivot].high))
        if _confirmed_pivot(bars, candidate_pivot, pivot_window, "low"):
            lows.append((candidate_pivot, bars[candidate_pivot].low))

        bar = bars[i]
        # Expire old unconfirmed setups deterministically.
        for direction in ("long", "short"):
            setup = pending.get(direction)
            if setup and i - int(setup["reclaim_index"]) > reclaim_window:
                pending.pop(direction, None)

        # Confirm a structural break only after a reclaim candle on an earlier bar.
        if "long" in pending and highs:
            setup = pending["long"]
            eligible = [(idx, level) for idx, level in highs if idx > int(setup["reclaim_index"])]
            if eligible and bar.close > eligible[-1][1]:
                entry_index = i + 1
                entry = bars[entry_index].open
                stop = float(setup["sweep_extreme"]) - stop_buffer
                risk = entry - stop
                if risk > 0 and math.isfinite(risk):
                    signals.append(ResearchSignal("long", int(setup["sweep_index"]),
                        int(setup["reclaim_index"]), i, entry_index, entry, stop,
                        entry + reward_risk * risk, float(setup["swept_level"]), reward_risk))
                pending.pop("long", None)

        if "short" in pending and lows:
            setup = pending["short"]
            eligible = [(idx, level) for idx, level in lows if idx > int(setup["reclaim_index"])]
            if eligible and bar.close < eligible[-1][1]:
                entry_index = i + 1
                entry = bars[entry_index].open
                stop = float(setup["sweep_extreme"]) + stop_buffer
                risk = stop - entry
                if risk > 0 and math.isfinite(risk):
                    signals.append(ResearchSignal("short", int(setup["sweep_index"]),
                        int(setup["reclaim_index"]), i, entry_index, entry, stop,
                        entry - reward_risk * risk, float(setup["swept_level"]), reward_risk))
                pending.pop("short", None)

        # A sweep/reclaim must use a previously confirmed pivot.
        if lows:
            level_idx, level = lows[-1]
            if level_idx < i and bar.low < level and bar.close > level:
                pending["long"] = {"sweep_index": i, "reclaim_index": i,
                                   "sweep_extreme": bar.low, "swept_level": level}
        if highs:
            level_idx, level = highs[-1]
            if level_idx < i and bar.high > level and bar.close < level:
                pending["short"] = {"sweep_index": i, "reclaim_index": i,
                                    "sweep_extreme": bar.high, "swept_level": level}

    # A post-generation gate keeps candidate detection independent from
    # context calculation while enforcing a strict point-in-time context check.
    return [
        signal for signal in signals
        if _context_direction(context_bars, parsed_times[signal.confirmation_index], pivot_window)
        == signal.direction
    ]
