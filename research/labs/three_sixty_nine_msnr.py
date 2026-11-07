"""Research-only 369/MSNR arithmetic and close-time primitives.

This module has no broker, capital, or order-routing dependencies. Strategy
qualification remains blocked until instrument mapping, swing provenance,
market data, and cost evidence are independently verified.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from math import isfinite
from zoneinfo import ZoneInfo


NEW_YORK = ZoneInfo("America/New_York")
RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
ORDER_SUBMISSION_PERMITTED = False


def digital_root(integer_price: int) -> int:
    """Return the base-10 digital root of a strictly positive integer."""
    if type(integer_price) is not int or integer_price <= 0:
        raise ValueError("DIGITAL_ROOT_REQUIRES_POSITIVE_INTEGER")
    return 1 + ((integer_price - 1) % 9)


def level_step_for_root(root: int) -> int:
    """Map a digital root to the approved 369 step size."""
    if type(root) is not int or root not in range(1, 10):
        raise ValueError("DIGITAL_ROOT_OUT_OF_RANGE")
    if root in (1, 4, 7):
        return 12
    if root in (2, 5, 8):
        return 15
    return 18


def build_369_levels(
    anchor_price: float,
    *,
    direction: str,
    level_count: int = 4,
) -> tuple[float, ...]:
    """Build levels from the protected swing anchor, preserving its fraction.

    LONG levels extend upward from a protected low; SHORT levels extend
    downward from a protected high. This helper does not quantize to an
    instrument tick: callers must validate tick precision separately.
    """
    if isinstance(anchor_price, bool):
        raise ValueError("369_ANCHOR_PRICE_INVALID")
    try:
        anchor = Decimal(str(anchor_price))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("369_ANCHOR_PRICE_INVALID") from exc
    if not anchor.is_finite() or anchor <= 0:
        raise ValueError("369_ANCHOR_PRICE_INVALID")
    if direction not in {"LONG", "SHORT"}:
        raise ValueError("369_DIRECTION_INVALID")
    if type(level_count) is not int or level_count < 4:
        raise ValueError("369_LEVEL_COUNT_MUST_BE_AT_LEAST_4")

    integer_part = int(anchor)
    step = level_step_for_root(digital_root(integer_part))
    sign = Decimal(1) if direction == "LONG" else Decimal(-1)
    return tuple(float(anchor + sign * Decimal(step * index)) for index in range(1, level_count + 1))


def _require_aware_timestamp(value: datetime, *, error_code: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(error_code)


def signal_close_is_eligible(close_timestamp: datetime) -> bool:
    """Check confirmed close time in New York's [09:45, 10:00) window."""
    _require_aware_timestamp(
        close_timestamp,
        error_code="SIGNAL_CLOSE_TIMESTAMP_MUST_BE_TIMEZONE_AWARE",
    )
    local = close_timestamp.astimezone(NEW_YORK)
    local_clock = local.timetz().replace(tzinfo=None)
    return time(9, 45) <= local_clock < time(10, 0)


def bar_close_timestamp(
    bar_open_timestamp: datetime,
    timeframe_seconds: int,
) -> datetime:
    """Derive close time from an open-labelled bar and declared duration."""
    _require_aware_timestamp(
        bar_open_timestamp,
        error_code="BAR_OPEN_TIMESTAMP_MUST_BE_TIMEZONE_AWARE",
    )
    if type(timeframe_seconds) is not int or timeframe_seconds <= 0:
        raise ValueError("TIMEFRAME_SECONDS_MUST_BE_POSITIVE_INTEGER")
    return bar_open_timestamp + timedelta(seconds=timeframe_seconds)



from dataclasses import dataclass
from statistics import fmean
from typing import Sequence

from research.labs.deterministic_intraday_strategies import (
    MSNRConfig,
    RegimeConfig,
    StrategyBar,
    _validate_bars,
    detect_msnr_liquidity_sweep,
)


def _parse_aware_iso(value: str, *, error_code: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(error_code) from exc
    _require_aware_timestamp(stamp, error_code=error_code)
    return stamp


@dataclass(frozen=True)
class ProtectedSwing:
    """Externally confirmed swing; this module does not infer swing structure."""

    direction: str
    anchor_price: float
    pivot_timestamp_utc: str
    confirmation_timestamp_utc: str
    source_rule_id: str
    last_input_bar_timestamp_utc: str

    def __post_init__(self) -> None:
        if self.direction not in {"LOW", "HIGH"}:
            raise ValueError("PROTECTED_SWING_DIRECTION_INVALID")
        if not isfinite(float(self.anchor_price)) or float(self.anchor_price) <= 0:
            raise ValueError("PROTECTED_SWING_ANCHOR_INVALID")
        if not isinstance(self.source_rule_id, str) or not self.source_rule_id.strip():
            raise ValueError("PROTECTED_SWING_SOURCE_RULE_REQUIRED")
        pivot = _parse_aware_iso(
            self.pivot_timestamp_utc, error_code="PROTECTED_SWING_PIVOT_TIMESTAMP_INVALID"
        )
        confirmed = _parse_aware_iso(
            self.confirmation_timestamp_utc,
            error_code="PROTECTED_SWING_CONFIRMATION_TIMESTAMP_INVALID",
        )
        last_input = _parse_aware_iso(
            self.last_input_bar_timestamp_utc,
            error_code="PROTECTED_SWING_LAST_INPUT_TIMESTAMP_INVALID",
        )
        if confirmed < pivot or last_input < pivot:
            raise ValueError("PROTECTED_SWING_PROVENANCE_ORDER_INVALID")


@dataclass(frozen=True)
class ThreeSixtyNineMSNRConfig:
    instrument_id: str
    tick_size: float
    price_scale: float
    instrument_mapping_verified: bool
    msnr_config: MSNRConfig
    regime_config: RegimeConfig = RegimeConfig()
    displacement_filter: bool = False
    ema_atr_filter: bool = False
    minimum_gross_r: float = 3.0
    level_count: int = 4
    version: str = "0.1.0"

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, str) or not self.instrument_id.strip():
            raise ValueError("369_INSTRUMENT_ID_REQUIRED")
        if not isfinite(float(self.tick_size)) or self.tick_size <= 0:
            raise ValueError("369_TICK_SIZE_INVALID")
        if not isfinite(float(self.price_scale)) or self.price_scale <= 0:
            raise ValueError("369_PRICE_SCALE_INVALID")
        if self.msnr_config.tick_size is None:
            raise ValueError("369_MSNR_TICK_SIZE_REQUIRED")
        if Decimal(str(self.msnr_config.tick_size)) != Decimal(str(self.tick_size)):
            raise ValueError("369_MSNR_TICK_SIZE_MISMATCH")
        if not isfinite(float(self.minimum_gross_r)) or self.minimum_gross_r < 3.0:
            raise ValueError("369_MINIMUM_GROSS_R_MUST_BE_AT_LEAST_3")
        if type(self.level_count) is not int or self.level_count < 4:
            raise ValueError("369_LEVEL_COUNT_MUST_BE_AT_LEAST_4")
        if not isinstance(self.instrument_mapping_verified, bool):
            raise ValueError("369_INSTRUMENT_MAPPING_STATUS_INVALID")


@dataclass(frozen=True)
class ThreeSixtyNineMSNRCandidate:
    strategy_id: str
    version: str
    instrument_id: str
    direction: str
    signal_close_timestamp_utc: str
    entry_timestamp_utc: str
    entry_price: float
    stop_price: float
    target_price: float
    gross_r: float
    variant_id: str
    target_selection_rule: str
    evidence_codes: tuple[str, ...]
    capital_authority: bool = False
    order_submission_permitted: bool = False

    @property
    def research_only(self) -> bool:
        return True


def _tick_aligned(price: float, tick_size: float) -> bool:
    try:
        ratio = Decimal(str(price)) / Decimal(str(tick_size))
    except (InvalidOperation, ZeroDivisionError):
        return False
    return ratio == ratio.to_integral_value()


def _ema(values: Sequence[float], period: int) -> float:
    alpha = 2.0 / (period + 1.0)
    result = float(values[0])
    for value in values[1:]:
        result = alpha * float(value) + (1.0 - alpha) * result
    return result


def _ema_atr_extended(bars: Sequence[StrategyBar]) -> bool | None:
    """Return True when extended, False when not, None when warm-up is missing."""
    if len(bars) < 15:
        return None
    ema20 = _ema([bar.close for bar in bars], 20)
    recent = bars[-15:]
    true_ranges = [
        max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        for previous, current in zip(recent, recent[1:])
    ]
    atr14 = fmean(true_ranges)
    if not isfinite(atr14) or atr14 <= 0:
        return None
    return abs(bars[-1].close - ema20) > 2.0 * atr14


def evaluate_369_msnr_candidate(
    bars: Sequence[StrategyBar],
    *,
    timeframe_seconds: int,
    protected_swing: ProtectedSwing,
    config: ThreeSixtyNineMSNRConfig,
) -> ThreeSixtyNineMSNRCandidate | None:
    """Compose a closed-bar MSNR signal with a verified swing and 369 target.

    The last bar is used only for its open as the next-bar entry. Signal
    detection and filters receive the preceding closed-bar prefix exclusively.
    """
    if not config.instrument_mapping_verified:
        return None
    if len(bars) < 2:
        return None
    _validate_bars(bars)
    signal_bars = tuple(bars[:-1])
    signal_bar = signal_bars[-1]
    next_bar = bars[-1]

    signal_open = _parse_aware_iso(
        signal_bar.timestamp_utc, error_code="SIGNAL_BAR_TIMESTAMP_INVALID"
    )
    next_open = _parse_aware_iso(
        next_bar.timestamp_utc, error_code="NEXT_BAR_TIMESTAMP_INVALID"
    )
    signal_close = bar_close_timestamp(signal_open, timeframe_seconds)
    if next_open < signal_close:
        return None
    if not signal_close_is_eligible(signal_close):
        return None

    pivot = _parse_aware_iso(
        protected_swing.pivot_timestamp_utc,
        error_code="PROTECTED_SWING_PIVOT_TIMESTAMP_INVALID",
    )
    confirmed = _parse_aware_iso(
        protected_swing.confirmation_timestamp_utc,
        error_code="PROTECTED_SWING_CONFIRMATION_TIMESTAMP_INVALID",
    )
    last_input = _parse_aware_iso(
        protected_swing.last_input_bar_timestamp_utc,
        error_code="PROTECTED_SWING_LAST_INPUT_TIMESTAMP_INVALID",
    )
    if (
        confirmed < pivot
        or last_input < pivot
        or confirmed > signal_close
        or last_input > signal_close
        or not protected_swing.source_rule_id.strip()
    ):
        return None

    msnr = detect_msnr_liquidity_sweep(
        signal_bars,
        config=config.msnr_config,
        regime_config=config.regime_config,
    )
    if msnr is None:
        return None
    expected_swing_side = "LOW" if msnr.direction == "LONG" else "HIGH"
    if protected_swing.direction != expected_swing_side:
        return None

    variant_parts = ["THREE_SIXTY_NINE_MSNR"]
    if config.displacement_filter:
        if len(signal_bars) < 4:
            return None
        prior_bodies = [
            abs(float(bar.close) - float(bar.open))
            for bar in signal_bars[-4:-1]
        ]
        mean_prior_body = fmean(prior_bodies)
        signal_body = abs(float(signal_bar.close) - float(signal_bar.open))
        if signal_body <= 1.5 * mean_prior_body:
            return None
        variant_parts.append("DISPLACEMENT")

    if config.ema_atr_filter:
        extended = _ema_atr_extended(signal_bars)
        if extended is None or extended:
            return None
        variant_parts.append("EMA_ATR_FILTERED")

    scale = float(config.price_scale)
    scaled_tick = float(config.tick_size) * scale
    anchor = float(protected_swing.anchor_price) * scale
    entry = float(next_bar.open) * scale
    stop = float(msnr.stop_reference_price) * scale
    if not all(_tick_aligned(price, scaled_tick) for price in (anchor, entry, stop)):
        return None

    levels = build_369_levels(
        anchor,
        direction=msnr.direction,
        level_count=config.level_count,
    )
    risk = entry - stop if msnr.direction == "LONG" else stop - entry
    if not isfinite(risk) or risk <= 0:
        return None

    eligible_targets: list[tuple[float, float]] = []
    for target in levels:
        if not _tick_aligned(target, scaled_tick):
            return None
        reward = target - entry if msnr.direction == "LONG" else entry - target
        if reward <= 0:
            continue
        gross_r = reward / risk
        if gross_r >= config.minimum_gross_r:
            eligible_targets.append((target, gross_r))
    if not eligible_targets:
        return None
    target, gross_r = eligible_targets[0]

    close_utc = signal_close.astimezone(timezone.utc).isoformat()
    return ThreeSixtyNineMSNRCandidate(
        strategy_id="THREE_SIXTY_NINE_MSNR",
        version=config.version,
        instrument_id=config.instrument_id,
        direction=msnr.direction,
        signal_close_timestamp_utc=close_utc,
        entry_timestamp_utc=next_bar.timestamp_utc,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        gross_r=gross_r,
        variant_id="_".join(variant_parts),
        target_selection_rule="NEAREST_369_LEVEL_MEETING_MINIMUM_GROSS_R",
        evidence_codes=tuple(msnr.evidence_codes) + (
            "PROTECTED_SWING_PROVENANCE_VERIFIED",
            "SIGNAL_CLOSE_TIME_ELIGIBLE",
            "NEXT_BAR_OPEN_ENTRY",
            "GROSS_TARGET_DISTANCE_AT_LEAST_3R",
        ),
        capital_authority=False,
        order_submission_permitted=False,
    )
