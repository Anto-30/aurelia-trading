"""Deterministic T4F x 369 primitives.

Only user-specified numerical rules are encoded here. Swing candidates are not
promoted to protected swings without a separately verified BOS/MSS annotation.
No component in this module has capital or order authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from typing import Sequence
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False

_STEP_BY_ROOT = {
    1: Decimal("12"), 4: Decimal("12"), 7: Decimal("12"),
    2: Decimal("15"), 5: Decimal("15"), 8: Decimal("15"),
    3: Decimal("18"), 6: Decimal("18"), 9: Decimal("18"),
}
_INSTRUMENT_MULTIPLIERS = {
    "XAUUSD": Decimal("1"),
    "NQ": Decimal("10"),
    "ES": Decimal("1"),
}


@dataclass(frozen=True)
class LevelProjection:
    instrument: str
    reference_price: Decimal
    integer_part: int
    digit_sum: int
    digital_root: int
    base_step: Decimal
    instrument_multiplier: Decimal
    scaled_step: Decimal
    calibration_status: str
    direction: str
    levels: tuple[Decimal, ...]


def _to_decimal(value: Decimal | int | float | str, field: str) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field}_INVALID") from exc
    if not result.is_finite():
        raise ValueError(f"{field}_MUST_BE_FINITE")
    return result


def digital_root_for_reference(price: Decimal | int | float | str) -> tuple[int, int, int]:
    """Return (integer_part, digit_sum, digital_root) using positive integer part."""
    value = _to_decimal(price, "REFERENCE_PRICE")
    if value <= 0:
        raise ValueError("REFERENCE_PRICE_MUST_BE_POSITIVE")
    integer_part = int(value.to_integral_value(rounding=ROUND_FLOOR))
    digit_sum = sum(int(character) for character in str(integer_part))
    reduced = digit_sum
    while reduced >= 10:
        reduced = sum(int(character) for character in str(reduced))
    if reduced == 0:
        raise ValueError("DIGITAL_ROOT_UNDEFINED_FOR_ZERO_REFERENCE")
    return integer_part, digit_sum, reduced


def calculate_369_step(
    price: Decimal | int | float | str,
    instrument: str,
    direction: str,
    num_levels: int = 4,
) -> LevelProjection:
    """Project levels using integer-part root selection and full-precision price."""
    normalized_instrument = instrument.strip().upper()
    normalized_direction = direction.strip().lower()
    if normalized_instrument not in _INSTRUMENT_MULTIPLIERS:
        raise ValueError("INSTRUMENT_MAPPING_UNDEFINED")
    if normalized_direction not in {"bullish", "bearish"}:
        raise ValueError("DIRECTION_MUST_BE_BULLISH_OR_BEARISH")
    if not isinstance(num_levels, int) or num_levels < 4:
        raise ValueError("AT_LEAST_FOUR_LEVELS_REQUIRED")

    reference = _to_decimal(price, "REFERENCE_PRICE")
    integer_part, digit_sum, root = digital_root_for_reference(reference)
    base_step = _STEP_BY_ROOT[root]
    multiplier = _INSTRUMENT_MULTIPLIERS[normalized_instrument]
    scaled_step = base_step * multiplier

    if normalized_direction == "bearish":
        levels = tuple(reference - (Decimal(n) * scaled_step) for n in range(1, num_levels + 1))
    else:
        levels = tuple(reference + (Decimal(n) * scaled_step) for n in range(1, num_levels + 1))

    calibration = (
        "USER_SPECIFIED"
        if normalized_instrument in {"XAUUSD", "NQ"}
        else "UNVERIFIED_PER_USER_SPEC"
    )
    return LevelProjection(
        instrument=normalized_instrument,
        reference_price=reference,
        integer_part=integer_part,
        digit_sum=digit_sum,
        digital_root=root,
        base_step=base_step,
        instrument_multiplier=multiplier,
        scaled_step=scaled_step,
        calibration_status=calibration,
        direction=normalized_direction,
        levels=levels,
    )


@dataclass(frozen=True)
class OHLC:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    @classmethod
    def from_values(cls, open_: object, high: object, low: object, close: object) -> "OHLC":
        bar = cls(
            _to_decimal(open_, "OPEN"),
            _to_decimal(high, "HIGH"),
            _to_decimal(low, "LOW"),
            _to_decimal(close, "CLOSE"),
        )
        if bar.high < max(bar.open, bar.close, bar.low):
            raise ValueError("OHLC_HIGH_INCONSISTENT")
        if bar.low > min(bar.open, bar.close, bar.high):
            raise ValueError("OHLC_LOW_INCONSISTENT")
        if min(bar.open, bar.high, bar.low, bar.close) <= 0:
            raise ValueError("OHLC_PRICES_MUST_BE_POSITIVE")
        return bar


def classify_m15_level_interaction(
    bar: OHLC,
    level: Decimal | int | float | str,
) -> str:
    """Classify observable candle interaction; never upgrades it to an entry signal.

    'BODY_CROSS_*' records a body crossing and close beyond a level, but cannot
    certify 'decisive' because the framework supplies no body-size threshold.
    """
    price_level = _to_decimal(level, "LEVEL")
    if bar.open < price_level and bar.close > price_level:
        return "BODY_CROSS_ABOVE_DECISIVENESS_UNDEFINED"
    if bar.open > price_level and bar.close < price_level:
        return "BODY_CROSS_BELOW_DECISIVENESS_UNDEFINED"
    if bar.open < price_level and bar.high > price_level and bar.close < price_level:
        return "UPPER_WICK_REJECTION"
    if bar.open > price_level and bar.low < price_level and bar.close > price_level:
        return "LOWER_WICK_REJECTION"
    return "NO_CLASSIFIABLE_INTERACTION"


@dataclass(frozen=True)
class PivotCandidate:
    pivot_index: int
    confirmation_index: int
    pivot_type: str
    price: Decimal
    status: str = "CANDIDATE_NOT_PROTECTED"


def detect_confirmed_pivot_candidates(
    highs: Sequence[object],
    lows: Sequence[object],
    *,
    left_bars: int,
    right_bars: int,
) -> list[PivotCandidate]:
    """Return confirmed mechanical pivot candidates with their first knowable index.

    This is intentionally NOT a Protected Swing detector. It does not infer BOS,
    MSS, displacement, or structure; callers must supply independent evidence.
    """
    if len(highs) != len(lows):
        raise ValueError("HIGH_LOW_LENGTH_MISMATCH")
    if left_bars < 1 or right_bars < 1:
        raise ValueError("PIVOT_WINDOWS_MUST_BE_POSITIVE")

    high_values = [_to_decimal(v, "HIGH") for v in highs]
    low_values = [_to_decimal(v, "LOW") for v in lows]
    if any(low <= 0 or high <= 0 for low, high in zip(low_values, high_values)):
        raise ValueError("BAR_PRICES_MUST_BE_POSITIVE")
    if any(low > high for low, high in zip(low_values, high_values)):
        raise ValueError("BAR_HIGH_LOW_INCONSISTENT")

    candidates: list[PivotCandidate] = []
    for pivot in range(left_bars, len(high_values) - right_bars):
        start = pivot - left_bars
        end = pivot + right_bars + 1
        h_window = high_values[start:end]
        l_window = low_values[start:end]
        pivot_high = high_values[pivot]
        pivot_low = low_values[pivot]

        # Unique extremum only; ties are not silently promoted to pivots.
        if h_window.count(pivot_high) == 1 and pivot_high == max(h_window):
            candidates.append(PivotCandidate(
                pivot_index=pivot,
                confirmation_index=pivot + right_bars,
                pivot_type="HIGH",
                price=pivot_high,
            ))
        if l_window.count(pivot_low) == 1 and pivot_low == min(l_window):
            candidates.append(PivotCandidate(
                pivot_index=pivot,
                confirmation_index=pivot + right_bars,
                pivot_type="LOW",
                price=pivot_low,
            ))
    return candidates



@dataclass(frozen=True)
class OpeningReferenceBias:
    day_open_relation: str
    day_open_action: str
    london_open_relation: str
    london_open_action: str
    combined_bias: str


def classify_opening_reference_bias(
    current_price: Decimal | int | float | str,
    day_open: Decimal | int | float | str,
    london_open: Decimal | int | float | str,
) -> OpeningReferenceBias:
    """Apply the user's above-open => look sell / below-open => look buy rule."""
    current = _to_decimal(current_price, "CURRENT_PRICE")
    day = _to_decimal(day_open, "DAY_OPEN")
    london = _to_decimal(london_open, "LONDON_OPEN")

    def relation(reference: Decimal) -> tuple[str, str]:
        if current > reference:
            return "ABOVE", "LOOK_FOR_SELL"
        if current < reference:
            return "BELOW", "LOOK_FOR_BUY"
        return "EQUAL", "NEUTRAL"

    day_relation, day_action = relation(day)
    london_relation, london_action = relation(london)
    if day_action == london_action == "LOOK_FOR_SELL":
        combined = "BEARISH"
    elif day_action == london_action == "LOOK_FOR_BUY":
        combined = "BULLISH"
    else:
        combined = "NEUTRAL"
    return OpeningReferenceBias(
        day_open_relation=day_relation,
        day_open_action=day_action,
        london_open_relation=london_relation,
        london_open_action=london_action,
        combined_bias=combined,
    )


def new_york_369_session_markers(session_date: date) -> tuple[tuple[str, str], ...]:
    """Return exact America/New_York marker times for the supplied 07:20-10:45 window.

    Fractions use the user's 205-minute session duration. These are exact
    mathematical markers, not a rounding rule for matching M1/M15 candles.
    """
    timezone = ZoneInfo("America/New_York")
    start = datetime.combine(session_date, time(7, 20), tzinfo=timezone)
    duration_seconds = Decimal(205 * 60)
    fractions = (
        ("0.000", Decimal("0")),
        ("0.315", Decimal("0.315")),
        ("0.630", Decimal("0.630")),
        ("0.810", Decimal("0.810")),
        ("1.000", Decimal("1")),
    )
    markers = []
    for label, fraction in fractions:
        offset_seconds = duration_seconds * fraction
        marker = start + timedelta(seconds=float(offset_seconds))
        markers.append((label, marker.isoformat()))
    return tuple(markers)


@dataclass(frozen=True)
class SMTResult:
    classification: str
    nq_made_lower_low: bool
    es_failed_to_make_lower_low: bool
    nq_made_higher_high: bool
    es_failed_to_make_higher_high: bool


def classify_nq_es_smt(
    *,
    nq_prior_high: Decimal | int | float | str,
    nq_prior_low: Decimal | int | float | str,
    nq_current_high: Decimal | int | float | str,
    nq_current_low: Decimal | int | float | str,
    es_prior_high: Decimal | int | float | str,
    es_prior_low: Decimal | int | float | str,
    es_current_high: Decimal | int | float | str,
    es_current_low: Decimal | int | float | str,
) -> SMTResult:
    """Apply the exact NQ-versus-ES higher-high/lower-low divergence rules."""
    values = {
        key: _to_decimal(value, key.upper())
        for key, value in locals().items()
    }
    nq_lower = values["nq_current_low"] < values["nq_prior_low"]
    es_no_lower = values["es_current_low"] >= values["es_prior_low"]
    nq_higher = values["nq_current_high"] > values["nq_prior_high"]
    es_no_higher = values["es_current_high"] <= values["es_prior_high"]
    bullish = nq_lower and es_no_lower
    bearish = nq_higher and es_no_higher
    classification = (
        "MIXED_SMT" if bullish and bearish else
        "BULLISH_SMT" if bullish else
        "BEARISH_SMT" if bearish else
        "NO_SMT"
    )
    return SMTResult(
        classification=classification,
        nq_made_lower_low=nq_lower,
        es_failed_to_make_lower_low=es_no_lower,
        nq_made_higher_high=nq_higher,
        es_failed_to_make_higher_high=es_no_higher,
    )


@dataclass(frozen=True)
class FairValueGapCandidate:
    direction: str
    first_bar_index: int
    third_bar_index: int
    gap_low: Decimal
    gap_high: Decimal
    midpoint: Decimal
    stop_invalidation_boundary: Decimal
    status: str = "FVG_CANDIDATE_RULE_REQUIRES_OWNER_FREEZE"


def first_aligned_fvg_candidate(
    bars: Sequence[OHLC],
    *,
    direction: str,
    confirmation_bar_index: int,
) -> FairValueGapCandidate | None:
    """Return the first strict three-candle FVG formed wholly after confirmation.

    The user requires the first aligned FVG but did not specify FVG boundaries.
    The classic 3-candle non-overlap definition is exposed as a named candidate
    only; it is not promoted to a frozen strategy rule.
    """
    normalized_direction = direction.strip().lower()
    if normalized_direction not in {"bullish", "bearish"}:
        raise ValueError("FVG_DIRECTION_INVALID")
    if confirmation_bar_index < -1:
        raise ValueError("FVG_CONFIRMATION_INDEX_INVALID")
    if any(not isinstance(bar, OHLC) for bar in bars):
        raise ValueError("FVG_BARS_MUST_BE_OHLC")
    for idx in range(2, len(bars)):
        first_idx = idx - 2
        if first_idx <= confirmation_bar_index:
            continue
        first = bars[first_idx]
        third = bars[idx]
        if normalized_direction == "bullish" and third.low > first.high:
            low = first.high
            high = third.low
            return FairValueGapCandidate(
                direction="BULLISH",
                first_bar_index=first_idx,
                third_bar_index=idx,
                gap_low=low,
                gap_high=high,
                midpoint=(low + high) / Decimal("2"),
                stop_invalidation_boundary=low,
            )
        if normalized_direction == "bearish" and third.high < first.low:
            low = third.high
            high = first.low
            return FairValueGapCandidate(
                direction="BEARISH",
                first_bar_index=first_idx,
                third_bar_index=idx,
                gap_low=low,
                gap_high=high,
                midpoint=(low + high) / Decimal("2"),
                stop_invalidation_boundary=high,
            )
    return None
