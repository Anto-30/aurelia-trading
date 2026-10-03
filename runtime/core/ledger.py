from __future__ import annotations

from threading import Lock

from .models import LedgerEvent


class InMemoryLedger:
    """Minimal single-process ledger interface used by the capital executor.

    Persistent production state is provided by PersistentLedger in
    runtime.core.persistent. This class exists for the explicit in-memory/test
    contract and does not create a second production ledger architecture.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: dict[str, LedgerEvent] = {}

    def post(self, event: LedgerEvent) -> bool:
        with self._lock:
            if event.event_id in self._events:
                return False
            self._events[event.event_id] = event
            return True

    def events(self) -> list[LedgerEvent]:
        with self._lock:
            return list(self._events.values())
