"""Fail-closed timer for successful runtime heartbeat logging."""
from __future__ import annotations

import math
from threading import Lock
from time import monotonic
from typing import Callable


class DeadManSwitch:
    """Trips when no accepted runtime heartbeat succeeds before the deadline.

    The trip is sticky for the lifetime of this object. A late heartbeat cannot
    clear it; recovery must restart/reauthorize through the canonical release path.
    This component denies execution and never grants capital authority.
    """

    ACCEPTED_SUCCESS_EVENTS = frozenset({"RUNTIME_HEARTBEAT", "TRADE_EXECUTION"})

    def __init__(self, timeout_seconds: float = 60.0, *, clock: Callable[[], float] = monotonic) -> None:
        if isinstance(timeout_seconds, bool) or not math.isfinite(float(timeout_seconds)) or timeout_seconds <= 0:
            raise ValueError("DEADMAN_TIMEOUT_MUST_BE_POSITIVE_AND_FINITE")
        self.timeout_seconds = float(timeout_seconds)
        self._clock = clock
        self._lock = Lock()
        self._last_success = self._clock()
        self._last_event = "INITIALIZED"
        self._tripped = False

    def record_success(self, event_type: str) -> bool:
        """Record a successful event; it is impossible to clear an existing trip."""
        if event_type not in self.ACCEPTED_SUCCESS_EVENTS:
            raise ValueError("DEADMAN_EVENT_TYPE_NOT_A_SUCCESS")
        with self._lock:
            if self._tripped:
                return False
            self._last_success = self._clock()
            self._last_event = event_type
            return True

    def expired(self) -> bool:
        with self._lock:
            return self._tripped or self._clock() - self._last_success >= self.timeout_seconds

    def trip_if_expired(self) -> bool:
        """Atomically trip once when the success deadline has expired."""
        with self._lock:
            if self._tripped or self._clock() - self._last_success < self.timeout_seconds:
                return False
            self._tripped = True
            return True

    @property
    def tripped(self) -> bool:
        with self._lock:
            return self._tripped

    @property
    def last_event(self) -> str:
        with self._lock:
            return self._last_event

    @property
    def age_seconds(self) -> float:
        with self._lock:
            return max(0.0, self._clock() - self._last_success)
