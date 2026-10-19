"""Deterministic 15-minute SMC Trend setup detector.

RESEARCH ONLY. It creates research candidates and pending-setup diagnostics;
it never connects to a broker, sizes capital, submits orders, or grants release
authority. Thresholds are starting hypotheses and require instrument-specific
walk-forward and cost validation before any promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from statistics import fmean
from typing import Literal, Sequence

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
STRATEGY_ID = "SMC_TREND_15M"
STRATEGY_VERSION = "0.1.0"


def _utc(value: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("BAR_TIMESTAMP_INVALID") from exc
    if stamp.tzinfo is None:
        raise ValueError("BAR_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")
    return stamp.astimezone(timezone.utc)


@dataclass(frozen=True)
class OHLCBar:
    """A completed OHLC bar; timestamp_utc is its close time, not open time."""

    timestamp_utc: str
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        _utc(self.timestamp_utc)
        prices = (self.open, self.high, self.low, self.close)
        if not all(isfinite(float(value)) and float(value) > 0 for value in prices):
            raise ValueError("BAR_PRICES_MUST_BE_FINITE_AND_POSITIVE")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("BAR_HIGH_INCONSISTENT")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("BAR_LOW_INCONSISTENT")


def validate_bars(bars: Sequence[OHLCBar]) -> None:
    previous: datetime | None = None
    for bar in bars:
        if not isinstance(bar, OHLCBar):
            raise ValueError("BAR_TYPE_INVALID")
        stamp = _utc(bar.timestamp_utc)
        if previous is not None and stamp <= previous:
            raise ValueError("BAR_TIMESTAMPS_MUST_BE_STRICTLY_INCREASING")
        previous = stamp


@dataclass(frozen=True)
class SMCConfig:
    """Starting configuration; default numerical thresholds are unqualified."""

    atr_period: int = 14
    swing_left_bars: int = 2
    swing_right_bars: int = 2
    displacement_atr_multiple: float = 1.5
    min_fvg_atr_multiple: float = 0.5
    order_block_lookback_bars: int = 8
    tick_size: float | None = None
    stop_buffer_ticks: float = 1.0
    entry_zone: Literal["FVG", "ORDER_BLOCK"] = "FVG"
    target_multiple_r: float = 2.0
    max_pending_bars: int = 12
    require_higher_timeframe_alignment: bool = True
    version: str = STRATEGY_VERSION

    def __post_init__(self) -> None:
        if self.atr_period < 2:
            raise ValueError("ATR_PERIOD_MUST_BE_AT_LEAST_2")
        if self.swing_left_bars < 1 or self.swing_right_bars < 1:
            raise ValueError("SWING_WIDTHS_MUST_BE_POSITIVE")
        if not isfinite(self.displacement_atr_multiple) or self.displacement_atr_multiple <= 0:
            raise ValueError("DISPLACEMENT_MULTIPLE_INVALID")
        if not isfinite(self.min_fvg_atr_multiple) or self.min_fvg_atr_multiple <= 0:
            raise ValueError("FVG_MULTIPLE_INVALID")
        if self.order_block_lookback_bars < 1:
            raise ValueError("ORDER_BLOCK_LOOKBACK_INVALID")
        if self.tick_size is not None and (
            not isfinite(self.tick_size) or self.tick_size <= 0
        ):
            raise ValueError("TICK_SIZE_INVALID")
        if not isfinite(self.stop_buffer_ticks) or self.stop_buffer_ticks < 0:
            raise ValueError("STOP_BUFFER_INVALID")
        if self.entry_zone not in ("FVG", "ORDER_BLOCK"):
            raise ValueError("ENTRY_ZONE_INVALID")
        if not isfinite(self.target_multiple_r) or self.target_multiple_r <= 0:
            raise ValueError("TARGET_MULTIPLE_INVALID")
        if self.max_pending_bars < 1:
            raise ValueError("MAX_PENDING_BARS_INVALID")


@dataclass(frozen=True)
class SwingPoint:
    index: int
    kind: Literal["HIGH", "LOW"]
    price: float
    confirmed_at_index: int


@dataclass(frozen=True)
class FairValueGap:
    direction: Literal["LONG", "SHORT"]
    first_bar_index: int
    third_bar_index: int
    lower_price: float
    upper_price: float
    width: float

    @property
    def midpoint(self) -> float:
        return (self.lower_price + self.upper_price) / 2.0


@dataclass(frozen=True)
class ResearchSetup:
    strategy_id: str
    strategy_version: str
    symbol: str
    direction: Literal["LONG", "SHORT"]
    structure_event: Literal["BOS", "CHOCH"]
    signal_timestamp_utc: str
    signal_close: float
    higher_timeframe_bias: str
    prior_structure_bias: str
    swing_reference_price: float
    atr: float
    displacement: float
    fvg_lower: float
    fvg_upper: float
    fvg_width: float
    order_block_timestamp_utc: str
    order_block_low: float
    order_block_high: float
    entry_zone: str
    entry_limit_reference: float
    stop_reference: float
    target_reference: float
    risk_distance: float
    target_multiple_r: float
    expires_after_bars: int
    research_only: bool = True
    capital_authority: bool = False
    order_submission_permitted: bool = False

    def as_payload(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "symbol": self.symbol,
            "direction": self.direction,
            "structure_event": self.structure_event,
            "signal_timestamp_utc": self.signal_timestamp_utc,
            "signal_close": self.signal_close,
            "higher_timeframe_bias": self.higher_timeframe_bias,
            "prior_structure_bias": self.prior_structure_bias,
            "swing_reference_price": self.swing_reference_price,
            "atr": self.atr,
            "displacement": self.displacement,
            "fvg_lower": self.fvg_lower,
            "fvg_upper": self.fvg_upper,
            "fvg_width": self.fvg_width,
            "order_block_timestamp_utc": self.order_block_timestamp_utc,
            "order_block_low": self.order_block_low,
            "order_block_high": self.order_block_high,
            "entry_zone": self.entry_zone,
            "entry_limit_reference": self.entry_limit_reference,
            "stop_reference": self.stop_reference,
            "target_reference": self.target_reference,
            "risk_distance": self.risk_distance,
            "target_multiple_r": self.target_multiple_r,
            "expires_after_bars": self.expires_after_bars,
            "research_only": True,
            "capital_authority": False,
            "order_submission_permitted": False,
        }


@dataclass(frozen=True)
class SetupStatus:
    status: Literal["PENDING", "ENTRY_LEVEL_TOUCHED", "INVALIDATED", "EXPIRED"]
    bars_elapsed: int
    reason: str


def wilder_atr(bars: Sequence[OHLCBar], period: int = 14) -> list[float | None]:
    """Return Wilder ATR values; indexes before warm-up are None."""
    validate_bars(bars)
    if period < 2:
        raise ValueError("ATR_PERIOD_MUST_BE_AT_LEAST_2")
    if len(bars) < period:
        return [None] * len(bars)

    true_ranges: list[float] = []
    for index, bar in enumerate(bars):
        if index == 0:
            true_ranges.append(bar.high - bar.low)
            continue
        previous_close = bars[index - 1].close
        true_ranges.append(max(
            bar.high - bar.low,
            abs(bar.high - previous_close),
            abs(bar.low - previous_close),
        ))

    output: list[float | None] = [None] * len(bars)
    output[period - 1] = fmean(true_ranges[:period])
    for index in range(period, len(bars)):
        prior_atr = output[index - 1]
        assert prior_atr is not None
        output[index] = (prior_atr * (period - 1) + true_ranges[index]) / period
    return output


def confirmed_swings(
    bars: Sequence[OHLCBar], *, left_bars: int = 2, right_bars: int = 2
) -> list[SwingPoint]:
    """Find confirmed strict pivots; no pivot uses bars after the supplied prefix."""
    validate_bars(bars)
    if left_bars < 1 or right_bars < 1:
        raise ValueError("SWING_WIDTHS_MUST_BE_POSITIVE")

    swings: list[SwingPoint] = []
    for index in range(left_bars, len(bars) - right_bars):
        left = bars[index - left_bars:index]
        right = bars[index + 1:index + right_bars + 1]
        high_neighbours = [bar.high for bar in (*left, *right)]
        low_neighbours = [bar.low for bar in (*left, *right)]
        if bars[index].high > max(high_neighbours):
            swings.append(SwingPoint(index, "HIGH", bars[index].high, index + right_bars))
        if bars[index].low < min(low_neighbours):
            swings.append(SwingPoint(index, "LOW", bars[index].low, index + right_bars))
    return sorted(swings, key=lambda point: (point.index, point.kind))


def structure_bias(
    bars: Sequence[OHLCBar], config: SMCConfig
) -> Literal["BULLISH", "BEARISH", "NEUTRAL"]:
    """Bias is HH+HL = bullish, LH+LL = bearish; otherwise neutral."""
    swings = confirmed_swings(
        bars,
        left_bars=config.swing_left_bars,
        right_bars=config.swing_right_bars,
    )
    highs = [point for point in swings if point.kind == "HIGH"]
    lows = [point for point in swings if point.kind == "LOW"]
    if len(highs) < 2 or len(lows) < 2:
        return "NEUTRAL"
    last_highs, last_lows = highs[-2:], lows[-2:]
    higher_highs = last_highs[1].price > last_highs[0].price
    higher_lows = last_lows[1].price > last_lows[0].price
    lower_highs = last_highs[1].price < last_highs[0].price
    lower_lows = last_lows[1].price < last_lows[0].price
    if higher_highs and higher_lows:
        return "BULLISH"
    if lower_highs and lower_lows:
        return "BEARISH"
    return "NEUTRAL"


def latest_fvg(
    bars: Sequence[OHLCBar], *, direction: Literal["LONG", "SHORT"],
    atr: float, min_atr_multiple: float,
) -> FairValueGap | None:
    """Detect the latest completed three-bar gap at the final bar."""
    validate_bars(bars)
    if len(bars) < 3:
        return None
    if not isfinite(atr) or atr <= 0 or not isfinite(min_atr_multiple) or min_atr_multiple <= 0:
        raise ValueError("FVG_THRESHOLD_INPUT_INVALID")

    first, third = bars[-3], bars[-1]
    if direction == "LONG" and first.high < third.low:
        lower, upper = first.high, third.low
    elif direction == "SHORT" and first.low > third.high:
        lower, upper = third.high, first.low
    else:
        return None

    width = upper - lower
    if width <= min_atr_multiple * atr:
        return None
    return FairValueGap(direction, len(bars) - 3, len(bars) - 1, lower, upper, width)


def detect_smc_setup(
    bars_15m: Sequence[OHLCBar],
    bars_1h: Sequence[OHLCBar],
    *,
    symbol: str,
    config: SMCConfig,
) -> ResearchSetup | None:
    """Create a candidate from the last closed 15m bar; never submit an order.

    Rules:
    - Confirmed swing levels use left/right pivot bars only.
    - BOS/CHoCH requires a directional close beyond a confirmed swing and a
      directional candle body >= displacement_atr_multiple * Wilder ATR.
    - The same close must complete a three-bar FVG wider than the configured ATR
      threshold.
    - The last opposing candle in the bounded lookback is the order block.
    - The 1h closed-bar structure bias must agree with the candidate direction
      by default. A future/unclosed 1h bar is excluded by close timestamp.
    - The entry, stop and 2R-style target are references for backtesting only.
    """
    validate_bars(bars_15m)
    validate_bars(bars_1h)
    if not symbol or not symbol.strip():
        raise ValueError("SYMBOL_REQUIRED")
    if config.tick_size is None:
        raise ValueError("VERIFIED_TICK_SIZE_REQUIRED")
    if len(bars_15m) < max(
        config.atr_period,
        config.swing_left_bars + config.swing_right_bars + 3,
        3,
    ):
        return None

    signal = bars_15m[-1]
    signal_time = _utc(signal.timestamp_utc)
    closed_1h = [bar for bar in bars_1h if _utc(bar.timestamp_utc) <= signal_time]
    htf_bias = structure_bias(closed_1h, config) if closed_1h else "NEUTRAL"
    if config.require_higher_timeframe_alignment and htf_bias not in ("BULLISH", "BEARISH"):
        return None

    atr_values = wilder_atr(bars_15m, config.atr_period)
    atr = atr_values[-1]
    if atr is None or atr <= 0:
        return None

    pivots = confirmed_swings(
        bars_15m,
        left_bars=config.swing_left_bars,
        right_bars=config.swing_right_bars,
    )
    current_index = len(bars_15m) - 1
    prior_highs = [p for p in pivots if p.kind == "HIGH" and p.index < current_index]
    prior_lows = [p for p in pivots if p.kind == "LOW" and p.index < current_index]
    if not prior_highs or not prior_lows:
        return None

    swing_high, swing_low = prior_highs[-1], prior_lows[-1]
    body = signal.close - signal.open
    if signal.close > swing_high.price and body > 0 and body >= config.displacement_atr_multiple * atr:
        direction: Literal["LONG", "SHORT"] = "LONG"
        reference_price = swing_high.price
    elif signal.close < swing_low.price and body < 0 and abs(body) >= config.displacement_atr_multiple * atr:
        direction = "SHORT"
        reference_price = swing_low.price
    else:
        return None

    if config.require_higher_timeframe_alignment and htf_bias != (
        "BULLISH" if direction == "LONG" else "BEARISH"
    ):
        return None

    fvg = latest_fvg(
        bars_15m,
        direction=direction,
        atr=atr,
        min_atr_multiple=config.min_fvg_atr_multiple,
    )
    if fvg is None:
        return None

    prior_bias = structure_bias(bars_15m[:-1], config)
    opposing_candles = [
        (index, bar)
        for index, bar in enumerate(bars_15m[max(0, current_index - config.order_block_lookback_bars):current_index],
                                    start=max(0, current_index - config.order_block_lookback_bars))
        if (bar.close < bar.open if direction == "LONG" else bar.close > bar.open)
    ]
    if not opposing_candles:
        return None
    ob_index, order_block = opposing_candles[-1]

    if direction == "LONG":
        event: Literal["BOS", "CHOCH"] = "CHOCH" if prior_bias == "BEARISH" else "BOS"
        stop = order_block.low - config.stop_buffer_ticks * config.tick_size
    else:
        event = "CHOCH" if prior_bias == "BULLISH" else "BOS"
        stop = order_block.high + config.stop_buffer_ticks * config.tick_size

    if config.entry_zone == "FVG":
        entry = fvg.midpoint
    else:
        entry = (order_block.low + order_block.high) / 2.0

    if direction == "LONG":
        risk = entry - stop
        if entry >= signal.close or risk <= 0:
            return None
        target = entry + config.target_multiple_r * risk
        if target <= signal.close:
            return None
    else:
        risk = stop - entry
        if entry <= signal.close or risk <= 0:
            return None
        target = entry - config.target_multiple_r * risk
        if target >= signal.close:
            return None

    return ResearchSetup(
        strategy_id=STRATEGY_ID,
        strategy_version=config.version,
        symbol=symbol,
        direction=direction,
        structure_event=event,
        signal_timestamp_utc=signal.timestamp_utc,
        signal_close=signal.close,
        higher_timeframe_bias=htf_bias,
        prior_structure_bias=prior_bias,
        swing_reference_price=reference_price,
        atr=atr,
        displacement=abs(body),
        fvg_lower=fvg.lower_price,
        fvg_upper=fvg.upper_price,
        fvg_width=fvg.width,
        order_block_timestamp_utc=order_block.timestamp_utc,
        order_block_low=order_block.low,
        order_block_high=order_block.high,
        entry_zone=config.entry_zone,
        entry_limit_reference=entry,
        stop_reference=stop,
        target_reference=target,
        risk_distance=risk,
        target_multiple_r=config.target_multiple_r,
        expires_after_bars=config.max_pending_bars,
    )


def assess_pending_setup(
    setup: ResearchSetup, subsequent_closed_bars: Sequence[OHLCBar]
) -> SetupStatus:
    """Assess only level-touch/invalidation, not an actual broker fill.

    If one OHLC bar both touches the entry and closes beyond the order-block
    boundary, invalidation wins conservatively. Price touching the level does
    not prove a tradable fill, queue priority, or execution price.
    """
    validate_bars(subsequent_closed_bars)
    signal_time = _utc(setup.signal_timestamp_utc)
    for elapsed, bar in enumerate(subsequent_closed_bars, start=1):
        if _utc(bar.timestamp_utc) <= signal_time:
            raise ValueError("FOLLOW_UP_BAR_NOT_AFTER_SIGNAL")
        invalidated = (
            bar.close < setup.order_block_low if setup.direction == "LONG"
            else bar.close > setup.order_block_high
        )
        if invalidated:
            return SetupStatus("INVALIDATED", elapsed, "CLOSE_BEYOND_ORDER_BLOCK")
        touched = bar.low <= setup.entry_limit_reference <= bar.high
        if touched:
            return SetupStatus("ENTRY_LEVEL_TOUCHED", elapsed, "PRICE_INTERSECTED_REFERENCE_LEVEL_ONLY")
        if elapsed >= setup.expires_after_bars:
            return SetupStatus("EXPIRED", elapsed, "PENDING_SETUP_TIME_TO_LIVE_EXCEEDED")
    return SetupStatus("PENDING", len(subsequent_closed_bars), "AWAITING_TOUCH_OR_INVALIDATION")
