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
