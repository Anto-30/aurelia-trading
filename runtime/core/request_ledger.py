"""Idempotency ledger for Deriv API request-response correlation."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RequestState(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"


@dataclass
class TrackedRequest:
    req_id: int
    request_type: str
    payload: dict[str, Any]
    created_at: float = field(default_factory=time.time)
    state: RequestState = RequestState.PENDING
    response: dict[str, Any] | None = None


class RequestLedger:
    """Tracks outgoing Deriv API requests for idempotency and reconciliation."""

    def __init__(self, max_pending_age_seconds: float = 30.0):
        self._counter: int = 0
        self._pending: dict[int, TrackedRequest] = {}
        self._max_pending_age = max_pending_age_seconds

    def create_request(
        self,
        request_type: str,
        payload: dict[str, Any],
        *,
        req_id: int | None = None,
    ) -> TrackedRequest:
        if req_id is None:
            self._counter += 1
            req_id = self._counter
        else:
            if not isinstance(req_id, int) or req_id <= 0:
                raise ValueError("REQUEST_ID_MUST_BE_POSITIVE_INTEGER")
            self._counter = max(self._counter, req_id)
        tracked = TrackedRequest(
            req_id=req_id,
            request_type=request_type,
            payload=payload,
        )
        self._pending[tracked.req_id] = tracked
        return tracked

    def confirm(self, req_id: int, response: dict[str, Any]) -> TrackedRequest | None:
        tracked = self._pending.pop(req_id, None)
        if tracked is not None:
            tracked.state = RequestState.CONFIRMED
            tracked.response = response
        return tracked

    def reject(self, req_id: int, response: dict[str, Any]) -> TrackedRequest | None:
        tracked = self._pending.pop(req_id, None)
        if tracked is not None:
            tracked.state = RequestState.REJECTED
            tracked.response = response
        return tracked

    def expire_stale(self) -> list[TrackedRequest]:
        """Mark requests older than max_pending_age as TIMEOUT and remove them."""
        now = time.time()
        expired: list[TrackedRequest] = []
        for req_id, tracked in list(self._pending.items()):
            if now - tracked.created_at > self._max_pending_age:
                tracked.state = RequestState.TIMEOUT
                expired.append(tracked)
                del self._pending[req_id]
        return expired

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def pending_requests(self) -> list[TrackedRequest]:
        return list(self._pending.values())
