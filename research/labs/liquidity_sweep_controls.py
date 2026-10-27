"""Research-only setup lifecycle and fail-closed execution guards.

This module has no broker client and cannot authorize capital. Datetimes must
be timezone-aware. Setup management is for simulation/observation only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from typing import Optional

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
LIVE_EXECUTION = False


def _aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def validate_live_timestamp(signal_time: datetime, current_time: datetime) -> bool:
    """Reject future-dated signals; equality is allowed for timestamp validation only."""
    _aware(signal_time, "signal_time")
    _aware(current_time, "current_time")
    if signal_time > current_time:
        raise ValueError(
            f"Lookahead detected: signal time {signal_time.isoformat()} "
            f"> current time {current_time.isoformat()}"
        )
    return True


@dataclass
class Setup:
    timestamp: datetime
    direction: str  # LONG or SHORT
    entry_price: float
    stop_loss: float
    target: float
    expiry: Optional[datetime] = None


class SetupManager:
    """Track unfilled research setups; this is not an order manager."""

    def __init__(self, expiry_minutes: int = 60):
        if isinstance(expiry_minutes, bool) or not isinstance(expiry_minutes, int) or expiry_minutes <= 0:
            raise ValueError("expiry_minutes must be a positive integer")
        self.active_setups: dict[str, Setup] = {}
        self.expiry_minutes = expiry_minutes

    @staticmethod
    def _validate_prices(setup: Setup) -> None:
        if setup.direction not in ("LONG", "SHORT"):
            raise ValueError("direction must be LONG or SHORT")
        values = (setup.entry_price, setup.stop_loss, setup.target)
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("setup prices must be finite")
        if setup.entry_price <= 0 or setup.stop_loss <= 0 or setup.target <= 0:
            raise ValueError("setup prices must be positive")
        if setup.direction == "LONG":
            valid = setup.stop_loss < setup.entry_price < setup.target
        else:
            valid = setup.target < setup.entry_price < setup.stop_loss
        if not valid:
            raise ValueError(f"invalid {setup.direction} stop/entry/target ordering")

    def add_setup(self, setup: Setup, current_time: datetime) -> bool:
        _aware(setup.timestamp, "setup.timestamp")
        _aware(current_time, "current_time")
        if setup.timestamp > current_time:
            raise ValueError("Lookahead detected: setup timestamp is in the future")
        self._validate_prices(setup)

        # Expire stale entries before applying duplicate rules.
        self.check_expiry_and_edge_cases(current_time, None, had_gap=False)
        existing = self.active_setups.get(setup.direction)
        if existing is not None:
            # A duplicate direction is blocked throughout the existing setup's
            # live interval; timestamp comparisons alone must not revive stale setups.
            if existing.expiry is not None and current_time < existing.expiry:
                return False

        setup.expiry = setup.timestamp + timedelta(minutes=self.expiry_minutes)
        if current_time >= setup.expiry:
            return False
        self.active_setups[setup.direction] = setup
        return True

    def check_expiry_and_edge_cases(
        self,
        current_time: datetime,
        current_price: float | None,
        had_gap: bool,
    ) -> list[str]:
        """Remove expired or invalidated setups and return the removed directions.

        A gap is treated as an invalidation if the observed price has crossed
        either boundary. No fill is inferred from a single price observation.
        """
        _aware(current_time, "current_time")
        if current_price is not None and not math.isfinite(float(current_price)):
            raise ValueError("current_price must be finite when provided")
        removed: list[str] = []
        for direction, setup in list(self.active_setups.items()):
            _aware(setup.timestamp, "setup.timestamp")
            if setup.expiry is None:
                # Fail closed on malformed state rather than raising AttributeError
                # or leaving an immortal setup in the active set.
                removed.append(direction)
                continue
            _aware(setup.expiry, "setup.expiry")
            invalid = current_time >= setup.expiry
            if current_price is not None:
                if direction == "LONG":
                    invalid = invalid or current_price <= setup.stop_loss or current_price >= setup.target
                elif direction == "SHORT":
                    invalid = invalid or current_price >= setup.stop_loss or current_price <= setup.target
                else:
                    invalid = True
            # A gap inside the setup's range does not automatically mean a hit.
            # If the supplied current price crossed a boundary, it is invalidated.
            if invalid:
                removed.append(direction)
        for direction in removed:
            self.active_setups.pop(direction, None)
        return removed


class LiveExecutionLock:
    """Explicitly deny live execution from research code.

    An environment variable must never supersede config/LIVE_LOCK.yaml or the
    canonical AURELIA release authority. This research module cannot unlock it.
    """

    def __init__(self) -> None:
        self.is_unlocked = False

    def can_execute(self) -> bool:
        raise PermissionError(
            "Live execution is blocked: research code has no capital authority; "
            "the canonical AURELIA release gate must remain fail-closed."
        )
