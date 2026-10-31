"""T4F x 369 research utilities.

Research-only diagnostics. This module does not identify BOS-protected swings,
generate FVG entries, calculate executable PnL, or authorize orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Iterable, Sequence

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
ORDER_SUBMISSION_PERMITTED = False

_BASE_STEPS = {
    1: 12.0, 4: 12.0, 7: 12.0,
    2: 15.0, 5: 15.0, 8: 15.0,
    3: 18.0, 6: 18.0, 9: 18.0,
}
_INSTRUMENT_SCALE = {"XAUUSD": 1.0, "NQ": 10.0, "ES": 1.0}


def digital_root_from_price(price: float) -> tuple[int, int, int]:
    """Return (integer_part, digit_sum, digital_root) using the integer part."""
    if not isfinite(float(price)) or float(price) <= 0:
        raise ValueError("REFERENCE_PRICE_MUST_BE_FINITE_AND_POSITIVE")
    integer_part = int(float(price))
    digit_sum = sum(int(ch) for ch in str(integer_part))
    root = 0 if integer_part == 0 else 1 + (integer_part - 1) % 9
    return integer_part, digit_sum, root


@dataclass(frozen=True)
class LevelProjection:
    instrument: str
    direction: str
    reference_price: float
    integer_part: int
    digit_sum: int
    digital_root: int
    base_step: float
    scaled_step: float
    levels: tuple[float, ...]
    es_scaling_unverified: bool


def project_369_levels(
    reference_price: float,
    *,
    instrument: str,
    direction: str,
    count: int = 4,
) -> LevelProjection:
    """Project levels from the complete reference price; step uses integer root."""
    symbol = instrument.upper()
    side = direction.lower()
    if symbol not in _INSTRUMENT_SCALE:
        raise ValueError("INSTRUMENT_NOT_SUPPORTED")
    if side not in {"bullish", "bearish"}:
        raise ValueError("DIRECTION_MUST_BE_BULLISH_OR_BEARISH")
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 100:
        raise ValueError("LEVEL_COUNT_OUT_OF_RANGE")
    integer_part, digit_sum, root = digital_root_from_price(reference_price)
    base = _BASE_STEPS[root]
    step = base * _INSTRUMENT_SCALE[symbol]
    sign = 1.0 if side == "bullish" else -1.0
    levels = tuple(float(reference_price) + sign * n * step for n in range(1, count + 1))
    return LevelProjection(
        symbol, side, float(reference_price), integer_part, digit_sum, root,
        base, step, levels, symbol == "ES",
    )


def _utc_timestamp(value: str | datetime) -> datetime:
    try:
        stamp = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("CANDLE_TIMESTAMP_INVALID") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("CANDLE_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return stamp.astimezone(timezone.utc)


@dataclass(frozen=True)
class Candle:
    timestamp: str | datetime
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        _utc_timestamp(self.timestamp)
        values = (self.open, self.high, self.low, self.close)
        if not all(isfinite(float(v)) and float(v) > 0 for v in values):
            raise ValueError("CANDLE_OHLC_MUST_BE_FINITE_AND_POSITIVE")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("CANDLE_HIGH_INCONSISTENT")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("CANDLE_LOW_INCONSISTENT")


@dataclass(frozen=True)
class CandleQuality:
    rows: int
    duplicate_timestamps: int
    out_of_order_timestamps: int
    missing_intervals: int
    largest_gap_seconds: int
    status: str


def validate_candles(
    candles: Sequence[Candle], *, interval_seconds: int
) -> CandleQuality:
    """Validate chronology and gaps; never forward-fill or silently drop rows."""
    if interval_seconds <= 0:
        raise ValueError("INTERVAL_SECONDS_MUST_BE_POSITIVE")
    stamps = [_utc_timestamp(c.timestamp) for c in candles]
    duplicates = len(stamps) - len(set(stamps))
    out_of_order = sum(stamps[i] < stamps[i - 1] for i in range(1, len(stamps)))
    missing = 0
    largest_gap = 0
    for previous, current in zip(stamps, stamps[1:]):
        delta = int((current - previous).total_seconds())
        if delta > interval_seconds:
            largest_gap = max(largest_gap, delta)
            # Count absent expected bars, not merely the number of gap events.
            missing += max(0, delta // interval_seconds - 1)
    valid = bool(candles) and duplicates == 0 and out_of_order == 0 and missing == 0
    return CandleQuality(
        len(candles), duplicates, out_of_order, missing, largest_gap,
        "PASS" if valid else "FAIL_CLOSED",
    )


@dataclass(frozen=True)
class ConfirmedPivot:
    kind: str
    pivot_index: int
    confirmed_at_index: int
    price: float


def detect_confirmed_pivots(
    candles: Sequence[Candle], *, left_bars: int = 5, right_bars: int = 5
) -> tuple[ConfirmedPivot, ...]:
    """Causal pivot events; a pivot is unavailable until right_bars have closed.

    This is only a mechanical pivot detector. It does not prove a BOS/MSS or
    establish a T4F protected swing.
    """
    if left_bars < 1 or right_bars < 1:
        raise ValueError("PIVOT_LOOKBACKS_MUST_BE_POSITIVE")
    quality = validate_candles(candles, interval_seconds=60)
    if quality.duplicate_timestamps or quality.out_of_order_timestamps:
        raise ValueError("PIVOT_INPUT_CHRONOLOGY_INVALID")
    events: list[ConfirmedPivot] = []
    for i in range(left_bars, len(candles) - right_bars):
        window = candles[i - left_bars:i + right_bars + 1]
        high = candles[i].high
        low = candles[i].low
        # Strict unique extrema avoid ambiguous equal-high/low plateaus.
        if sum(c.high == high for c in window) == 1 and all(high > c.high for j, c in enumerate(window) if j != left_bars):
            events.append(ConfirmedPivot("HIGH", i, i + right_bars, high))
        if sum(c.low == low for c in window) == 1 and all(low < c.low for j, c in enumerate(window) if j != left_bars):
            events.append(ConfirmedPivot("LOW", i, i + right_bars, low))
    return tuple(events)


@dataclass(frozen=True)
class LevelTouch:
    level_number: int
    level_price: float
    first_touch_index: int
    bars_after_pivot_confirmation: int


def scan_level_touches(
    candles: Sequence[Candle],
    *,
    pivot: ConfirmedPivot,
    projection: LevelProjection,
    max_bars_after_confirmation: int,
    tolerance_fraction: float = 0.0,
) -> tuple[LevelTouch, ...]:
    """Descriptive level-touch scan, starting only after pivot confirmation.

    Touches are not entries, reversals, profitable trades, or evidence of edge.
    """
    if not 0 <= tolerance_fraction < 0.5:
        raise ValueError("TOLERANCE_FRACTION_OUT_OF_RANGE")
    if max_bars_after_confirmation < 1:
        raise ValueError("FORWARD_WINDOW_MUST_BE_POSITIVE")
    if pivot.kind == "HIGH" and projection.direction != "bearish":
        raise ValueError("PIVOT_DIRECTION_MISMATCH")
    if pivot.kind == "LOW" and projection.direction != "bullish":
        raise ValueError("PIVOT_DIRECTION_MISMATCH")
    start = pivot.confirmed_at_index + 1
    stop = min(len(candles), start + max_bars_after_confirmation)
    found: list[LevelTouch] = []
    for n, level in enumerate(projection.levels, start=1):
        band = abs(level) * tolerance_fraction
        for index in range(start, stop):
            candle = candles[index]
            if candle.low <= level + band and candle.high >= level - band:
                found.append(LevelTouch(n, level, index, index - pivot.confirmed_at_index))
                break
    return tuple(found)


def performance_metrics(rows: Iterable[dict[str, float]]) -> dict[str, float | int | str]:
    """Compute trade metrics from already-costed, realized trade rows.

    Required keys: pnl_net, r_multiple. Caller must supply chronologically
    ordered, non-overlapping trades and include all costs in pnl_net.
    """
    data = list(rows)
    if len(data) < 30:
        return {"status": "INSUFFICIENT_SAMPLE", "trades": len(data)}
    pnls: list[float] = []
    rs: list[float] = []
    for row in data:
        pnl, r = float(row["pnl_net"]), float(row["r_multiple"])
        if not isfinite(pnl) or not isfinite(r):
            raise ValueError("TRADE_METRICS_MUST_BE_FINITE")
        pnls.append(pnl)
        rs.append(r)
    gross_profit = sum(x for x in pnls if x > 0)
    gross_loss = abs(sum(x for x in pnls if x < 0))
    equity = peak = 0.0
    max_drawdown = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
    wins = sum(x > 0 for x in pnls)
    return {
        "status": "DESCRIPTIVE_ONLY",
        "trades": len(data),
        "win_rate": wins / len(data),
        "expectancy_r": sum(rs) / len(rs),
        "profit_factor": gross_profit / gross_loss if gross_loss else float("inf"),
        "max_drawdown_currency": max_drawdown,
        "net_pnl": sum(pnls),
    }
