"""Research-only price-visit activity profile.

This module does NOT calculate traded volume-at-price. Each valid observation
contributes one count to a price bin. Do not use its outputs to authorize orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Iterable, Sequence


@dataclass(frozen=True)
class PriceObservation:
    timestamp: int
    price: str | int | float | Decimal


@dataclass(frozen=True)
class ActivityProfile:
    semantics_label: str
    data_source_kind: str
    symbol: str
    as_of_time: int
    anchor_start_time: int
    tick_size: str
    bin_width_ticks: int
    value_area_fraction: str
    observation_count: int
    activity_poc: str
    activity_vah: str
    activity_val: str
    bins: tuple[tuple[int, int], ...]
    raw_observation_sha256: str
    algorithm_version: str = "tick-activity-profile-v1"
    live_eligible: bool = False

    def to_dict(self) -> dict:
        result = {
            "semantics_label": self.semantics_label,
            "data_source_kind": self.data_source_kind,
            "symbol": self.symbol,
            "as_of_time": self.as_of_time,
            "anchor_start_time": self.anchor_start_time,
            "tick_size": self.tick_size,
            "bin_width_ticks": self.bin_width_ticks,
            "value_area_fraction": self.value_area_fraction,
            "observation_count": self.observation_count,
            "activity_poc": self.activity_poc,
            "activity_vah": self.activity_vah,
            "activity_val": self.activity_val,
            "bins": [{"bin_index": index, "observed_price_updates": count}
                     for index, count in self.bins],
            "raw_observation_sha256": self.raw_observation_sha256,
            "algorithm_version": self.algorithm_version,
            "live_eligible": self.live_eligible,
        }
        return result


def _decimal(value: str | int | float | Decimal, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"INVALID_{field.upper()}") from exc
    if not parsed.is_finite():
        raise ValueError(f"INVALID_{field.upper()}")
    return parsed


def _price_to_tick(price: Decimal, tick_size: Decimal) -> int:
    ticks = price / tick_size
    rounded = ticks.to_integral_value(rounding=ROUND_HALF_UP)
    # Reject prices that cannot be represented by the instrument tick size.
    if abs(ticks - rounded) > Decimal("0.0000001"):
        raise ValueError("PRICE_NOT_ALIGNED_TO_TICK_SIZE")
    return int(rounded)


def calculate_tick_activity_profile(
    observations: Iterable[PriceObservation],
    *,
    symbol: str,
    tick_size: str | int | float | Decimal,
    bin_width_ticks: int,
    anchor_start_time: int,
    as_of_time: int,
    value_area_fraction: str | Decimal = "0.70",
) -> ActivityProfile:
    """Build a deterministic activity-count profile using only [anchor, as-of].

    Inputs must be chronologically ordered. Identical timestamps are permitted;
    the source may publish more than one observation at its timestamp resolution.
    This function cannot verify source completeness, freshness, or provenance.
    Callers must perform those checks separately and reject invalid coverage.
    """
    if not symbol or not isinstance(symbol, str):
        raise ValueError("INVALID_SYMBOL")
    if not isinstance(bin_width_ticks, int) or isinstance(bin_width_ticks, bool) or bin_width_ticks < 1:
        raise ValueError("INVALID_BIN_WIDTH_TICKS")
    if not isinstance(anchor_start_time, int) or not isinstance(as_of_time, int):
        raise ValueError("INVALID_TIME_BOUNDARY")
    if anchor_start_time > as_of_time:
        raise ValueError("ANCHOR_AFTER_AS_OF")
    tick = _decimal(tick_size, "tick_size")
    if tick <= 0:
        raise ValueError("INVALID_TICK_SIZE")
    fraction = _decimal(value_area_fraction, "value_area_fraction")
    if not Decimal("0") < fraction <= Decimal("1"):
        raise ValueError("INVALID_VALUE_AREA_FRACTION")

    selected: list[tuple[int, int, str]] = []
    last_timestamp: int | None = None
    for observation in observations:
        if not isinstance(observation.timestamp, int):
            raise ValueError("INVALID_TIMESTAMP")
        if last_timestamp is not None and observation.timestamp < last_timestamp:
            raise ValueError("NON_MONOTONIC_TIMESTAMPS")
        last_timestamp = observation.timestamp
        if observation.timestamp < anchor_start_time or observation.timestamp > as_of_time:
            continue
        price = _decimal(observation.price, "price")
        tick_index = _price_to_tick(price, tick)
        bin_index = tick_index // bin_width_ticks
        selected.append((observation.timestamp, bin_index, str(price.normalize())))

    if not selected:
        raise ValueError("NO_OBSERVATIONS_IN_PROFILE_WINDOW")

    counts: dict[int, int] = {}
    for _, bin_index, _ in selected:
        counts[bin_index] = counts.get(bin_index, 0) + 1

    # Deterministic POC tie-break: lowest-price bin first.
    poc = min(counts, key=lambda idx: (-counts[idx], idx))
    low = high = poc
    total = sum(counts.values())
    covered = counts[poc]
    target = fraction * total

    # Expand the contiguous value area by the larger adjacent count. If tied,
    # choose the lower-price bin. Stop only after reaching the requested share.
    while Decimal(covered) < target:
        lower_count = counts.get(low - 1, -1)
        upper_count = counts.get(high + 1, -1)
        if lower_count < 0 and upper_count < 0:
            break
        if lower_count >= upper_count:
            low -= 1
            covered += counts[low]
        else:
            high += 1
            covered += counts[high]

    canonical = json.dumps(
        [{"timestamp": ts, "bin_index": idx, "price": price}
         for ts, idx, price in selected],
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    digest = sha256(canonical).hexdigest()

    def bin_price(index: int) -> str:
        return str((tick * Decimal(index * bin_width_ticks)).normalize())

    return ActivityProfile(
        semantics_label="PRICE_VISIT_ACTIVITY_PROXY",
        data_source_kind="TICK_PRICE_OBSERVATIONS",
        symbol=symbol,
        as_of_time=as_of_time,
        anchor_start_time=anchor_start_time,
        tick_size=str(tick.normalize()),
        bin_width_ticks=bin_width_ticks,
        value_area_fraction=str(fraction.normalize()),
        observation_count=len(selected),
        activity_poc=bin_price(poc),
        activity_vah=bin_price(high + 1),
        activity_val=bin_price(low),
        bins=tuple(sorted(counts.items())),
        raw_observation_sha256=digest,
    )
