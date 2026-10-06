from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class CircuitBreaker:
    """Consecutive-failure circuit with timed half-open recovery.

    The breaker fails closed: once the failure threshold is reached, transport
    calls are rejected until the recovery window elapses. Only the configured
    number of half-open probe requests may cross the boundary.
    """

    failure_threshold: int = 5
    recovery_timeout_seconds: float = 60.0
    half_open_max_requests: int = 1
    open: bool = False
    failures: int = 0
    last_failure_at: float | None = None
    _half_open_requests: int = 0

    def __post_init__(self) -> None:
        self.failure_threshold = max(1, int(self.failure_threshold))
        self.recovery_timeout_seconds = max(0.0, float(self.recovery_timeout_seconds))
        self.half_open_max_requests = max(1, int(self.half_open_max_requests))

    def allow_request(self) -> bool:
        if not self.open:
            return True
        if self.last_failure_at is None:
            return False
        if time.monotonic() - self.last_failure_at < self.recovery_timeout_seconds:
            return False
        if self._half_open_requests >= self.half_open_max_requests:
            return False
        self._half_open_requests += 1
        return True

    def record_failure(self) -> bool:
        self.failures += 1
        self.last_failure_at = time.monotonic()
        if self.open:
            self._half_open_requests = 0
            return True
        if self.failures >= self.failure_threshold:
            self.open = True
            self._half_open_requests = 0
        return self.open

    def record_success(self) -> None:
        self.failures = 0
        self.open = False
        self.last_failure_at = None
        self._half_open_requests = 0

    def permit_new_submission(self) -> bool:
        """Compatibility gate for capital submissions.

        Transport-level calls are also gated by allow_request(); callers that
        submit capital should not issue a second circuit check immediately
        before the transport call.
        """
        return self.allow_request()

    @property
    def tripped(self) -> bool:
        return self.open

    @property
    def reason(self) -> str | None:
        return "CIRCUIT_BREAKER_OPEN" if self.open else None
