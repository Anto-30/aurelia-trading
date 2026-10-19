"""Research-only tick-activity profile primitives for AURELIA.

Counts observed price-tick records per price bin. Does not measure contracts traded,
notional turnover, order-book depth, or centralized exchange volume. No transport or
execution authority is included.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor, isfinite
from typing import Any, Iterable, Mapping

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False
PROFILE_KIND = "TICK_ACTIVITY_PROXY"


class VolumeProfileInputError(ValueError):
    """Input data or profile parameters are invalid."""


@dataclass(frozen=True)
class ProfileBin:
    index: int
    lower_edge: float
    upper_edge: float
    midpoint: float
    tick_count: int


@dataclass(frozen=True)
class NodeCandidate:
    kind: str
    bin_index: int
    price: float
    tick_count: int
    detection_method: str = "ADJACENT_BIN_RELATIVE_HEURISTIC_V1"


@dataclass(frozen=True)
class TickActivityProfile:
    schema: str
    profile_kind: str
    research_only: bool
    capital_authority: bool
    live_execution: bool
    instrument: str
    data_source: str
    binning_method: str
    bin_width: float
    total_ticks: int
    profile_start_epoch: float
    profile_end_epoch: float
    poc: float
    vah: float
    val: float
    poc_bin_index: int
    vah_bin_index: int
    val_bin_index: int
    value_area_fraction_requested: float
    value_area_fraction_actual: float
    value_area_tick_count: int
    bins: tuple[ProfileBin, ...]
    limitations: tuple[str, ...]


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise VolumeProfileInputError(f"{field.upper()}_INVALID")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise VolumeProfileInputError(f"{field.upper()}_INVALID") from exc
    if not isfinite(number):
        raise VolumeProfileInputError(f"{field.upper()}_NONFINITE")
    return number


def _make_edges(
    prices: list[float], *, num_bins: int, bin_width: float | None
) -> tuple[list[float], str]:
    low, high = min(prices), max(prices)
    if bin_width is not None:
        width = _finite_number(bin_width, "bin_width")
        if width <= 0:
            raise VolumeProfileInputError("BIN_WIDTH_MUST_BE_POSITIVE")
        start = floor(low / width) * width
        bin_count = max(1, int(ceil((high - start) / width)))
        edges = [start + i * width for i in range(bin_count + 1)]
        while edges[-1] < high:
            edges.append(edges[-1] + width)
        return edges, "FIXED_PRICE_WIDTH"

    if isinstance(num_bins, bool) or not isinstance(num_bins, int) or num_bins < 1:
        raise VolumeProfileInputError("NUM_BINS_MUST_BE_POSITIVE_INTEGER")
    if high == low:
        epsilon = max(abs(low) * 1e-9, 1e-6)
        low, high = low - epsilon, high + epsilon
        method = "EQUAL_WIDTH_RANGE_DEGENERATE"
    else:
        method = "EQUAL_WIDTH_SAMPLE_RANGE"
    width = (high - low) / num_bins
    edges = [low + i * width for i in range(num_bins)] + [high]
    return edges, method


def calculate_tick_activity_profile(
    ticks: Iterable[Mapping[str, Any]],
    *,
    instrument: str = "UNKNOWN",
    data_source: str = "UNVERIFIED",
    value_area_fraction: float = 0.70,
    num_bins: int = 100,
    bin_width: float | None = None,
) -> TickActivityProfile:
    """Compute deterministic POC/VAH/VAL from observed tick counts.

    Each record requires numeric price and epoch fields. A pandas DataFrame can be
    passed as df.to_dict(orient="records") without making pandas a runtime dependency.
    Fixed-width bins are preferred for comparisons; sample-range bins are exploratory.

    POC ties resolve to the lowest-price bin. Value-area expansion begins at POC,
    adds the larger adjacent bin, and expands both sides on ties to ensure progress
    through empty bins. VAH/VAL are outer edges of included bins; POC is the midpoint.
    """
    fraction = _finite_number(value_area_fraction, "value_area_fraction")
    if not 0 < fraction <= 1:
        raise VolumeProfileInputError("VALUE_AREA_FRACTION_OUT_OF_RANGE")
    if not isinstance(instrument, str) or not instrument.strip():
        raise VolumeProfileInputError("INSTRUMENT_REQUIRED")
    if not isinstance(data_source, str) or not data_source.strip():
        raise VolumeProfileInputError("DATA_SOURCE_REQUIRED")

    rows: list[tuple[float, float]] = []
    for tick in ticks:
        if not isinstance(tick, Mapping):
            raise VolumeProfileInputError("TICK_RECORD_MUST_BE_MAPPING")
        if "price" not in tick or "epoch" not in tick:
            raise VolumeProfileInputError("TICK_PRICE_AND_EPOCH_REQUIRED")
        price = _finite_number(tick["price"], "price")
        epoch = _finite_number(tick["epoch"], "epoch")
        if epoch < 0:
            raise VolumeProfileInputError("EPOCH_MUST_BE_NONNEGATIVE")
        rows.append((epoch, price))
    if not rows:
        raise VolumeProfileInputError("NO_TICK_DATA")

    rows.sort(key=lambda row: row[0])
    epochs = [row[0] for row in rows]
    prices = [row[1] for row in rows]
    edges, binning_method = _make_edges(prices, num_bins=num_bins, bin_width=bin_width)
    bin_count = len(edges) - 1
    if bin_count < 1 or any(not isfinite(edge) for edge in edges):
        raise VolumeProfileInputError("PRICE_BINS_INVALID")
    if any(edges[i] >= edges[i + 1] for i in range(bin_count)):
        raise VolumeProfileInputError("PRICE_BINS_NOT_STRICTLY_INCREASING")

    counts = [0] * bin_count
    first_edge = edges[0]
    width = (edges[-1] - edges[0]) / bin_count
    for price in prices:
        index = int(floor((price - first_edge) / width))
        index = min(bin_count - 1, max(0, index))
        counts[index] += 1
    total_ticks = sum(counts)
    if total_ticks != len(rows) or total_ticks <= 0:
        raise VolumeProfileInputError("TICK_COUNT_RECONCILIATION_FAILED")

    # max() returns the first occurrence: lowest-price bin breaks POC ties.
    poc_index = max(range(bin_count), key=lambda idx: counts[idx])
    lower_index = upper_index = poc_index
    value_area_ticks = counts[poc_index]
    target_ticks = total_ticks * fraction
    while value_area_ticks < target_ticks and (
        lower_index > 0 or upper_index < bin_count - 1
    ):
        left_count = counts[lower_index - 1] if lower_index > 0 else None
        right_count = counts[upper_index + 1] if upper_index < bin_count - 1 else None
        if left_count is None:
            upper_index += 1
            value_area_ticks += counts[upper_index]
        elif right_count is None:
            lower_index -= 1
            value_area_ticks += counts[lower_index]
        elif left_count == right_count:
            lower_index -= 1
            upper_index += 1
            value_area_ticks += counts[lower_index] + counts[upper_index]
        elif left_count > right_count:
            lower_index -= 1
            value_area_ticks += counts[lower_index]
        else:
            upper_index += 1
            value_area_ticks += counts[upper_index]

    bins = tuple(
        ProfileBin(
            index=i, lower_edge=edges[i], upper_edge=edges[i + 1],
            midpoint=(edges[i] + edges[i + 1]) / 2.0, tick_count=counts[i],
        )
        for i in range(bin_count)
    )
    actual_width = (
        _finite_number(bin_width, "bin_width")
        if binning_method == "FIXED_PRICE_WIDTH" else width
    )
    return TickActivityProfile(
        schema="aurelia.tick_activity_profile.v1",
        profile_kind=PROFILE_KIND,
        research_only=True,
        capital_authority=False,
        live_execution=False,
        instrument=instrument.strip(),
        data_source=data_source.strip(),
        binning_method=binning_method,
        bin_width=actual_width,
        total_ticks=total_ticks,
        profile_start_epoch=epochs[0],
        profile_end_epoch=epochs[-1],
        poc=bins[poc_index].midpoint,
        vah=bins[upper_index].upper_edge,
        val=bins[lower_index].lower_edge,
        poc_bin_index=poc_index,
        vah_bin_index=upper_index,
        val_bin_index=lower_index,
        value_area_fraction_requested=fraction,
        value_area_fraction_actual=value_area_ticks / total_ticks,
        value_area_tick_count=value_area_ticks,
        bins=bins,
        limitations=(
            "Counts observed tick records; it does not measure traded contracts, notional, or exchange volume.",
            "A tick-activity profile is not a standalone entry signal or evidence of institutional participation.",
            "HVN/LVN outputs are version-labelled heuristics marked CANDIDATE and require separate qualification.",
            "This module has no broker connection, capital authority, or live execution path.",
        ),
    )


def classify_price_context(price: float, profile: TickActivityProfile) -> str:
    """Label a price relative to the value area, not a trade signal."""
    value = _finite_number(price, "price")
    if value > profile.vah:
        return "ABOVE_VAH"
    if value < profile.val:
        return "BELOW_VAL"
    return "INSIDE_VALUE_AREA"


def profile_to_dict(profile: TickActivityProfile) -> dict[str, Any]:
    """Produce a JSON-serializable profile payload for research evidence."""
    return {
        "schema": profile.schema,
        "profile_kind": profile.profile_kind,
        "research_only": profile.research_only,
        "capital_authority": profile.capital_authority,
        "live_execution": profile.live_execution,
        "instrument": profile.instrument,
        "data_source": profile.data_source,
        "binning_method": profile.binning_method,
        "bin_width": profile.bin_width,
        "total_ticks": profile.total_ticks,
        "profile_start_epoch": profile.profile_start_epoch,
        "profile_end_epoch": profile.profile_end_epoch,
        "poc": profile.poc,
        "vah": profile.vah,
        "val": profile.val,
        "poc_bin_index": profile.poc_bin_index,
        "vah_bin_index": profile.vah_bin_index,
        "val_bin_index": profile.val_bin_index,
        "value_area_fraction_requested": profile.value_area_fraction_requested,
        "value_area_fraction_actual": profile.value_area_fraction_actual,
        "value_area_tick_count": profile.value_area_tick_count,
        "bins": [
            {"index": item.index, "lower_edge": item.lower_edge,
             "upper_edge": item.upper_edge, "midpoint": item.midpoint,
             "tick_count": item.tick_count}
            for item in profile.bins
        ],
        "limitations": list(profile.limitations),
    }


def detect_node_candidates(
    profile: TickActivityProfile,
    *,
    hvn_min_relative_peak: float = 0.35,
    lvn_max_relative_neighbors: float = 0.50,
) -> tuple[NodeCandidate, ...]:
    """Return heuristic HVN/LVN candidates, never entry signals.

    Candidates use tick counts, not traded volume. An HVN candidate is an interior
    local peak at least hvn_min_relative_peak of the global peak count. An LVN
    candidate is an interior local trough no more than lvn_max_relative_neighbors
    of both neighbors. Threshold sensitivity and OOS stability remain mandatory.
    """
    hvn_floor = _finite_number(hvn_min_relative_peak, "hvn_min_relative_peak")
    lvn_ceiling = _finite_number(lvn_max_relative_neighbors, "lvn_max_relative_neighbors")
    if not 0 < hvn_floor <= 1:
        raise VolumeProfileInputError("HVN_THRESHOLD_OUT_OF_RANGE")
    if not 0 <= lvn_ceiling < 1:
        raise VolumeProfileInputError("LVN_THRESHOLD_OUT_OF_RANGE")
    counts = [item.tick_count for item in profile.bins]
    if len(counts) < 3:
        return ()
    peak_count = max(counts)
    if peak_count <= 0:
        return ()
    nonzero = [index for index, count in enumerate(counts) if count > 0]
    if not nonzero:
        return ()
    first_nonzero, last_nonzero = nonzero[0], nonzero[-1]
    result: list[NodeCandidate] = []
    for index in range(1, len(counts) - 1):
        left, current, right = counts[index - 1], counts[index], counts[index + 1]
        if (current > 0 and current >= left and current >= right
                and (current > left or current > right)
                and current >= peak_count * hvn_floor):
            result.append(NodeCandidate(
                kind="HVN_CANDIDATE", bin_index=index,
                price=profile.bins[index].midpoint, tick_count=current,
            ))
        if (first_nonzero < index < last_nonzero and left > 0 and right > 0
                and current < left and current < right
                and current <= min(left, right) * lvn_ceiling):
            result.append(NodeCandidate(
                kind="LVN_CANDIDATE", bin_index=index,
                price=profile.bins[index].midpoint, tick_count=current,
            ))
    return tuple(sorted(result, key=lambda node: (node.bin_index, node.kind)))
