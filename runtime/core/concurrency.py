from __future__ import annotations

from contextlib import contextmanager
from threading import Lock

class SingleExecutionSlot:
    def __init__(self):
        self._lock=Lock()
    @contextmanager
    def acquire(self):
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("CONCURRENT_EXECUTION_ATTEMPT")
        try:
            yield
        finally:
            self._lock.release()
