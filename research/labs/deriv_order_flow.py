"""Deriv price/tick-direction proxies and event-conditioned triple-barrier labels.

Research-only. Deriv historical tick prices are not trade prints or traded volume.
This module does not calculate genuine aggressor delta, depth OFI, or traded-volume
profile, and it has no broker transport or capital authority.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from math import floor, isfinite
from typing import Iterable, Literal, Mapping, Sequence

Side = Literal["LONG", "SHORT"]
BarrierTouch = Literal["PROFIT_TARGET", "STOP_LOSS", "VERTICAL"]


class OrderFlowDataError(ValueError):
    """Raised for malformed or unsupported market-data inputs."""


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OrderFlowDataError(f"{name.upper()}_MUST_BE_NUMERIC")
    result = float(value)
    if not isfinite(result):
        raise OrderFlowDataError(f"{name.upper()}_MUST_BE_FINITE")
    return result


def _sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


@dataclass(frozen=True)
class Tick:
    """One observed price update; timestamp is Unix seconds."""

    timestamp: float
    price: float
    bid: float | None = None
    ask: float | None = None


@dataclass(frozen=True)
class TickFeature:
    timestamp: float
    price: float
    tick_direction: int
    signed_tick_count: int
    cumulative_signed_tick_count: int
    signed_tick_count_60s: int
    signed_tick_count_900s: int
    tick_count_60s: int
    tick_count_900s: int
    spread: float | None


@dataclass(frozen=True)
class TickFrequencyContext:
    price_bin: int
    visits: int
    occupied_bins: int
    status: str


@dataclass(frozen=True)
class PriceBar:
    """OHLC bar; timestamp is the bar's Unix-second close time."""

    timestamp: float
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class LabelEvent:
    """An MSNR/event trigger known after the close of event_index."""

    event_index: int
    side: Side


@dataclass(frozen=True)
class TripleBarrierLabel:
    event_index: int
    entry_index: int
    exit_index: int
    side: Side
    label: int
    touch: BarrierTouch
    entry_price: float
    exit_price: float
    directional_return: float
    elapsed_seconds: float


def parse_ticks_history_response(payload: Mapping[str, object]) -> tuple[Tick, ...]:
    """Parse documented history.prices and history.times arrays.

    This parser does not infer volume, bid/ask, or aggressor side from missing fields.
    """
    if not isinstance(payload, Mapping):
        raise OrderFlowDataError("DERIV_RESPONSE_MUST_BE_OBJECT")
    if payload.get("error") is not None:
        raise OrderFlowDataError("DERIV_API_REQUEST_FAILED")
    history = payload.get("history")
    if not isinstance(history, Mapping):
        raise OrderFlowDataError("DERIV_HISTORY_OBJECT_MISSING")
    prices = history.get("prices")
    times = history.get("times")
    if not _sequence(prices) or not _sequence(times):
        raise OrderFlowDataError("DERIV_HISTORY_PRICES_OR_TIMES_MISSING")
    if len(prices) != len(times):
        raise OrderFlowDataError("DERIV_HISTORY_PRICE_TIME_LENGTH_MISMATCH")

    ticks: list[Tick] = []
    for index, (raw_time, raw_price) in enumerate(zip(times, prices)):
        timestamp = _number(raw_time, f"times_{index}")
        price = _number(raw_price, f"prices_{index}")
        if timestamp < 0 or price <= 0:
            raise OrderFlowDataError(f"DERIV_HISTORY_VALUE_OUT_OF_RANGE_AT_{index}")
        ticks.append(Tick(timestamp=timestamp, price=price))
    return tuple(ticks)


def parse_live_tick_response(payload: Mapping[str, object]) -> Tick:
    """Parse an individual live tick; bid and ask remain optional."""
    if not isinstance(payload, Mapping):
        raise OrderFlowDataError("DERIV_TICK_RESPONSE_MUST_BE_OBJECT")
    raw_tick = payload.get("tick")
    if not isinstance(raw_tick, Mapping):
        raise OrderFlowDataError("DERIV_TICK_OBJECT_MISSING")
    timestamp = _number(raw_tick.get("epoch"), "tick_epoch")
    price = _number(raw_tick.get("quote"), "tick_quote")
    if timestamp < 0 or price <= 0:
        raise OrderFlowDataError("DERIV_TICK_VALUE_OUT_OF_RANGE")
    raw_bid = raw_tick.get("bid")
    raw_ask = raw_tick.get("ask")
    bid = None if raw_bid is None else _number(raw_bid, "tick_bid")
    ask = None if raw_ask is None else _number(raw_ask, "tick_ask")
    if (bid is not None and bid <= 0) or (ask is not None and ask <= 0):
        raise OrderFlowDataError("DERIV_TICK_BID_ASK_OUT_OF_RANGE")
    if bid is not None and ask is not None and ask < bid:
        raise OrderFlowDataError("DERIV_TICK_ASK_BELOW_BID")
    return Tick(timestamp=timestamp, price=price, bid=bid, ask=ask)


def _validated_ticks(ticks: Iterable[Tick]) -> tuple[Tick, ...]:
    rows = tuple(ticks)
    previous_timestamp: float | None = None
    for index, row in enumerate(rows):
        if not isinstance(row, Tick):
            raise OrderFlowDataError(f"TICK_OBJECT_INVALID_AT_{index}")
        timestamp = _number(row.timestamp, f"tick_timestamp_{index}")
        price = _number(row.price, f"tick_price_{index}")
        if timestamp < 0 or price <= 0:
            raise OrderFlowDataError(f"TICK_VALUE_OUT_OF_RANGE_AT_{index}")
        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise OrderFlowDataError("TICK_TIMESTAMPS_MUST_BE_NONDECREASING")
        previous_timestamp = timestamp
        if row.bid is not None and row.ask is not None:
            bid = _number(row.bid, f"tick_bid_{index}")
            ask = _number(row.ask, f"tick_ask_{index}")
            if bid <= 0 or ask < bid:
                raise OrderFlowDataError(f"TICK_SPREAD_INVALID_AT_{index}")
        elif row.bid is not None and _number(row.bid, f"tick_bid_{index}") <= 0:
            raise OrderFlowDataError(f"TICK_BID_INVALID_AT_{index}")
        elif row.ask is not None and _number(row.ask, f"tick_ask_{index}") <= 0:
            raise OrderFlowDataError(f"TICK_ASK_INVALID_AT_{index}")
    return rows


def compute_tick_features(ticks: Iterable[Tick]) -> tuple[TickFeature, ...]:
    """Calculate signed tick-count proxies over trailing 60s and 900s windows.

    Up-ticks count +1, down-ticks -1, and unchanged prices count 0. These are
    observed quote/price directions, not traded volume or true aggressor delta.
    Window boundaries include ticks exactly 60 or 900 seconds old.
    """
    rows = _validated_ticks(ticks)
    queue_60: deque[tuple[float, int]] = deque()
    queue_900: deque[tuple[float, int]] = deque()
    cumulative = 0
    prior_price: float | None = None
    result: list[TickFeature] = []

    for tick in rows:
        direction = 0
        if prior_price is not None:
            direction = 1 if tick.price > prior_price else -1 if tick.price < prior_price else 0
        prior_price = tick.price
        cumulative += direction

        queue_60.append((tick.timestamp, direction))
        queue_900.append((tick.timestamp, direction))
        cutoff_60 = tick.timestamp - 60.0
        cutoff_900 = tick.timestamp - 900.0
        while queue_60 and queue_60[0][0] < cutoff_60:
            queue_60.popleft()
        while queue_900 and queue_900[0][0] < cutoff_900:
            queue_900.popleft()

        spread = None
        if tick.bid is not None and tick.ask is not None:
            spread = float(tick.ask) - float(tick.bid)

        result.append(TickFeature(
            timestamp=float(tick.timestamp),
            price=float(tick.price),
            tick_direction=direction,
            signed_tick_count=direction,
            cumulative_signed_tick_count=cumulative,
            signed_tick_count_60s=sum(value for _, value in queue_60),
            signed_tick_count_900s=sum(value for _, value in queue_900),
            tick_count_60s=len(queue_60),
            tick_count_900s=len(queue_900),
            spread=spread,
        ))
    return tuple(result)


def _quantile(values: Sequence[int], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise OrderFlowDataError("PROFILE_COUNTS_EMPTY")
    position = (len(ordered) - 1) * q
    lower = int(floor(position))
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def tick_frequency_context(
    ticks: Iterable[Tick],
    index: int,
    *,
    lookback_seconds: float = 900.0,
    bin_width: float,
    low_quantile: float = 0.25,
    high_quantile: float = 0.75,
) -> TickFrequencyContext:
    """Classify recent price-bin visitation, not a traded-volume profile.

    Only rows at or before index are considered, preventing future leakage.
    HVN/LVN statuses are explicitly named as tick-frequency proxies.
    """
    rows = _validated_ticks(ticks)
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(rows):
        raise OrderFlowDataError("PROFILE_INDEX_OUT_OF_RANGE")
    lookback = _number(lookback_seconds, "profile_lookback")
    width = _number(bin_width, "profile_bin_width")
    low_q = _number(low_quantile, "profile_low_quantile")
    high_q = _number(high_quantile, "profile_high_quantile")
    if lookback <= 0 or width <= 0:
        raise OrderFlowDataError("PROFILE_LOOKBACK_AND_BIN_WIDTH_MUST_BE_POSITIVE")
    if not 0 <= low_q < high_q <= 1:
        raise OrderFlowDataError("PROFILE_QUANTILES_INVALID")

    current = rows[index]
    cutoff = current.timestamp - lookback
    recent = [row for row in rows[:index + 1] if row.timestamp >= cutoff]
    bin_ids = [int(floor(row.price / width)) for row in recent]
    counts = Counter(bin_ids)
    current_bin = int(floor(current.price / width))
    visits = counts[current_bin]
    occupied = len(counts)

    if occupied < 2:
        status = "INSUFFICIENT_VARIATION"
    else:
        values = list(counts.values())
        low = _quantile(values, low_q)
        high = _quantile(values, high_q)
        if visits < low and visits < high:
            status = "LVN_TICK_FREQUENCY_PROXY"
        elif visits > high and visits > low:
            status = "HVN_TICK_FREQUENCY_PROXY"
        else:
            status = "MID_TICK_FREQUENCY_PROXY"
    return TickFrequencyContext(
        price_bin=current_bin,
        visits=visits,
        occupied_bins=occupied,
        status=status,
    )


def detect_price_delta_divergence(
    prices: Sequence[float],
    cumulative_signed_tick_count: Sequence[float],
    *,
    lookback: int,
) -> str | None:
    """Detect a causal extreme/imbalance divergence using proxy tick-count delta.

    A bearish result requires a new price high and lower proxy cumulative delta;
    a bullish result requires a new price low and higher proxy cumulative delta.
    This is a heuristic, not exchange aggressor delta or proof of absorption.
    """
    if len(prices) != len(cumulative_signed_tick_count):
        raise OrderFlowDataError("DIVERGENCE_INPUT_LENGTH_MISMATCH")
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 2:
        raise OrderFlowDataError("DIVERGENCE_LOOKBACK_MUST_BE_AT_LEAST_TWO")
    if len(prices) <= lookback:
        return None
    px = [_number(value, "divergence_price") for value in prices]
    delta = [_number(value, "divergence_delta") for value in cumulative_signed_tick_count]
    if any(value <= 0 for value in px):
        raise OrderFlowDataError("DIVERGENCE_PRICE_MUST_BE_POSITIVE")

    prior_start = len(px) - lookback - 1
    prior_end = len(px) - 1
    prior_prices = px[prior_start:prior_end]
    high_offset = max(range(len(prior_prices)), key=lambda offset: prior_prices[offset])
    low_offset = min(range(len(prior_prices)), key=lambda offset: prior_prices[offset])
    prior_high_index = prior_start + high_offset
    prior_low_index = prior_start + low_offset

    if px[-1] > px[prior_high_index] and delta[-1] < delta[prior_high_index]:
        return "BEARISH_PRICE_DELTA_DIVERGENCE_PROXY"
    if px[-1] < px[prior_low_index] and delta[-1] > delta[prior_low_index]:
        return "BULLISH_PRICE_DELTA_DIVERGENCE_PROXY"
    return None



@dataclass(frozen=True)
class ConfluenceAssessment:
    """Research proposal only; it cannot authorize or submit an order."""

    research_eligible: bool
    side: Side | None
    reason: str


def evaluate_msnr_order_flow_confluence(
    msnr_side: str | None,
    divergence: str | None,
    *,
    market_structure_aligned: bool,
) -> ConfluenceAssessment:
    """Require independently detected MSNR context plus matching proxy trigger.

    This function is intentionally not an MSNR detector: the caller must pass a
    separately detected, point-in-time MSNR direction and a valid key-level/context
    decision. Tick-direction divergence is only a noisy proxy, not true order flow.
    research_eligible is a research filter, not runtime or capital authorization.
    """
    if not market_structure_aligned:
        return ConfluenceAssessment(False, None, "MSNR_CONTEXT_NOT_ALIGNED")
    if msnr_side not in ("LONG", "SHORT"):
        return ConfluenceAssessment(False, None, "MSNR_EVENT_MISSING_OR_INVALID")
    expected = {
        "LONG": "BULLISH_PRICE_DELTA_DIVERGENCE_PROXY",
        "SHORT": "BEARISH_PRICE_DELTA_DIVERGENCE_PROXY",
    }[msnr_side]
    if divergence is None:
        return ConfluenceAssessment(False, None, "ORDER_FLOW_PROXY_TRIGGER_MISSING")
    if divergence != expected:
        return ConfluenceAssessment(False, None, "ORDER_FLOW_PROXY_DIRECTION_MISMATCH")
    return ConfluenceAssessment(
        True,
        msnr_side,  # type: ignore[arg-type]
        "MSNR_CONTEXT_AND_TICK_DIRECTION_DIVERGENCE_PROXY_ALIGNED",
    )

def _validated_bars(bars: Iterable[PriceBar]) -> tuple[PriceBar, ...]:
    rows = tuple(bars)
    if len(rows) < 2:
        raise OrderFlowDataError("AT_LEAST_TWO_BARS_REQUIRED")
    previous_timestamp: float | None = None
    for index, bar in enumerate(rows):
        if not isinstance(bar, PriceBar):
            raise OrderFlowDataError(f"BAR_OBJECT_INVALID_AT_{index}")
        timestamp = _number(bar.timestamp, f"bar_timestamp_{index}")
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise OrderFlowDataError("BAR_TIMESTAMPS_MUST_STRICTLY_INCREASE")
        previous_timestamp = timestamp
        opening = _number(bar.open, f"bar_open_{index}")
        high = _number(bar.high, f"bar_high_{index}")
        low = _number(bar.low, f"bar_low_{index}")
        close = _number(bar.close, f"bar_close_{index}")
        if min(opening, high, low, close) <= 0 or low > min(opening, close) or high < max(opening, close) or low > high:
            raise OrderFlowDataError(f"BAR_OHLC_INVALID_AT_{index}")
    return rows


def label_triple_barrier(
    bars: Iterable[PriceBar],
    events: Iterable[LabelEvent],
    target_volatility: Sequence[float],
    *,
    pt_sl: tuple[float, float] = (1.5, 1.0),
    max_horizon: int = 10,
) -> tuple[TripleBarrierLabel, ...]:
    """Label event-conditioned outcomes with target distances known at event close.

    The event is known only after its bar closes, so entry starts at the next
    bar's open. target_volatility[event_index] must be computed using information
    available by that close. If both barriers are crossed within one OHLC bar,
    stop-loss wins conservatively. Stop gaps use the worse opening price.
    Incomplete vertical horizons without an earlier touch are omitted.
    """
    rows = _validated_bars(bars)
    signals = tuple(events)
    if len(target_volatility) != len(rows):
        raise OrderFlowDataError("TARGET_VOLATILITY_LENGTH_MISMATCH")
    if not isinstance(pt_sl, tuple) or len(pt_sl) != 2:
        raise OrderFlowDataError("PT_SL_MUST_HAVE_TWO_MULTIPLIERS")
    pt = _number(pt_sl[0], "profit_take_multiple")
    sl = _number(pt_sl[1], "stop_loss_multiple")
    if pt <= 0 or sl <= 0:
        raise OrderFlowDataError("PT_SL_MULTIPLIERS_MUST_BE_POSITIVE")
    if isinstance(max_horizon, bool) or not isinstance(max_horizon, int) or max_horizon < 1:
        raise OrderFlowDataError("MAX_HORIZON_MUST_BE_POSITIVE_INTEGER")

    seen: set[int] = set()
    output: list[TripleBarrierLabel] = []
    for event in signals:
        if not isinstance(event, LabelEvent):
            raise OrderFlowDataError("LABEL_EVENT_INVALID")
        idx = event.event_index
        if isinstance(idx, bool) or not isinstance(idx, int) or idx < 0 or idx >= len(rows) - 1:
            raise OrderFlowDataError("EVENT_REQUIRES_A_FOLLOWING_BAR")
        if idx in seen:
            raise OrderFlowDataError("DUPLICATE_LABEL_EVENT")
        seen.add(idx)
        if event.side not in ("LONG", "SHORT"):
            raise OrderFlowDataError("EVENT_SIDE_INVALID")
        target = _number(target_volatility[idx], f"target_volatility_{idx}")
        if target <= 0:
            raise OrderFlowDataError("TARGET_VOLATILITY_MUST_BE_POSITIVE")

        entry_index = idx + 1
        entry_price = float(rows[entry_index].open)
        direction = 1.0 if event.side == "LONG" else -1.0
        profit_price = entry_price + direction * target * pt
        stop_price = entry_price - direction * target * sl
        horizon_end = entry_index + max_horizon - 1
        last_index = min(len(rows) - 1, horizon_end)
        touch: BarrierTouch | None = None
        exit_index: int | None = None
        exit_price: float | None = None

        for j in range(entry_index, last_index + 1):
            bar = rows[j]
            if event.side == "LONG":
                if bar.open <= stop_price:
                    touch, exit_index, exit_price = "STOP_LOSS", j, float(bar.open)
                elif bar.open >= profit_price:
                    touch, exit_index, exit_price = "PROFIT_TARGET", j, profit_price
                else:
                    stop_hit = bar.low <= stop_price
                    target_hit = bar.high >= profit_price
                    if stop_hit:
                        touch, exit_index, exit_price = "STOP_LOSS", j, stop_price
                    elif target_hit:
                        touch, exit_index, exit_price = "PROFIT_TARGET", j, profit_price
            else:
                if bar.open >= stop_price:
                    touch, exit_index, exit_price = "STOP_LOSS", j, float(bar.open)
                elif bar.open <= profit_price:
                    touch, exit_index, exit_price = "PROFIT_TARGET", j, profit_price
                else:
                    stop_hit = bar.high >= stop_price
                    target_hit = bar.low <= profit_price
                    if stop_hit:
                        touch, exit_index, exit_price = "STOP_LOSS", j, stop_price
                    elif target_hit:
                        touch, exit_index, exit_price = "PROFIT_TARGET", j, profit_price
            if touch is not None:
                break

        if touch is None:
            if last_index != horizon_end:
                continue
            touch = "VERTICAL"
            exit_index = last_index
            exit_price = float(rows[last_index].close)

        if touch is None or exit_index is None or exit_price is None:
            raise OrderFlowDataError("BARRIER_EXIT_INVARIANT_FAILED")
        directional_return = direction * (exit_price - entry_price) / entry_price
        if touch == "PROFIT_TARGET":
            label = 1
        elif touch == "STOP_LOSS":
            label = -1
        else:
            label = 1 if directional_return > 0 else -1 if directional_return < 0 else 0
        output.append(TripleBarrierLabel(
            event_index=idx,
            entry_index=entry_index,
            exit_index=exit_index,
            side=event.side,
            label=label,
            touch=touch,
            entry_price=entry_price,
            exit_price=exit_price,
            directional_return=directional_return,
            elapsed_seconds=float(rows[exit_index].timestamp - rows[idx].timestamp),
        ))
    return tuple(output)
