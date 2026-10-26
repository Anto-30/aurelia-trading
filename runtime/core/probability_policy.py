"""Canonical hard probability policy for AURELIA trade decisions.

Calibration metrics may evaluate predictions throughout [0, 1]. This module
defines the narrower range eligible to proceed through the trade-authorization
chain. Values are rejected, never clipped.
"""
from __future__ import annotations

from math import isfinite


MIN_PROBABILITY = 0.55
MAX_PROBABILITY = 0.75


def probability_is_valid(probability: object) -> bool:
    """Return True only for finite numeric values in the inclusive 0.55–0.75 band."""
    if isinstance(probability, bool) or not isinstance(probability, (int, float)):
        return False
    try:
        value = float(probability)
    except (TypeError, ValueError, OverflowError):
        return False
    return isfinite(value) and MIN_PROBABILITY <= value <= MAX_PROBABILITY
