"""Deterministic setup lifecycle manager for research-only strategies.

This module manages signal/setup lifetimes only. It has no broker, capital,
or order-submission authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class ActiveSetup:
    setup_id: str
    session_id: str
    created_bar_index: int
    expires_after_bars: int
    payload: Any = None


class SetupManager:
    """Track setups, expire them by bar index, and deduplicate per session.

    A setup created at bar N remains eligible through bar N + X. It expires
    when the observed bar index is greater than N + X. A setup ID can be
    registered only once per session, including after it has expired or fired.
    Reusing an ID in a different session is allowed.
    """

    def __init__(self, default_expiry_bars: int = 3) -> None:
        self._validate_bar_count(default_expiry_bars, "SETUP_EXPIRY_BARS_INVALID")
        self.default_expiry_bars = default_expiry_bars
        self._active: dict[tuple[str, str], ActiveSetup] = {}
        self._seen: set[tuple[str, str]] = set()
        self._last_bar: dict[str, int] = {}
        self._lock = RLock()

    @staticmethod
    def _validate_bar_count(value: int, error_code: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(error_code)

    @staticmethod
    def _validate_identity(setup_id: str, session_id: str) -> None:
        if not isinstance(setup_id, str) or not setup_id.strip():
            raise ValueError("SETUP_ID_REQUIRED")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("SETUP_SESSION_ID_REQUIRED")

    @staticmethod
    def _validate_index(bar_index: int) -> None:
        if isinstance(bar_index, bool) or not isinstance(bar_index, int) or bar_index < 0:
            raise ValueError("SETUP_BAR_INDEX_INVALID")

    def register(
        self,
        setup_id: str,
        session_id: str,
        bar_index: int,
        *,
        payload: Any = None,
        expires_after_bars: int | None = None,
    ) -> bool:
        """Register a setup once per session; return False for duplicate IDs."""
        self._validate_identity(setup_id, session_id)
        self._validate_index(bar_index)
        ttl = self.default_expiry_bars if expires_after_bars is None else expires_after_bars
        self._validate_bar_count(ttl, "SETUP_EXPIRY_BARS_INVALID")
        key = (session_id, setup_id)
        with self._lock:
            previous = self._last_bar.get(session_id)
            if previous is not None and bar_index < previous:
                raise ValueError("SETUP_BAR_INDEX_OUT_OF_ORDER")
            if key in self._seen:
                return False
            self._last_bar[session_id] = bar_index
            self._seen.add(key)
            self._active[key] = ActiveSetup(setup_id, session_id, bar_index, ttl, payload)
            return True

    def advance(self, session_id: str, bar_index: int) -> tuple[ActiveSetup, ...]:
        """Advance one session and return setups that expired at this index."""
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("SETUP_SESSION_ID_REQUIRED")
        self._validate_index(bar_index)
        with self._lock:
            previous = self._last_bar.get(session_id)
            if previous is not None and bar_index < previous:
                raise ValueError("SETUP_BAR_INDEX_OUT_OF_ORDER")
            self._last_bar[session_id] = bar_index
            expired = []
            for key, setup in tuple(self._active.items()):
                if setup.session_id == session_id and bar_index - setup.created_bar_index > setup.expires_after_bars:
                    expired.append(setup)
                    del self._active[key]
            return tuple(sorted(expired, key=lambda item: item.setup_id))

    def mark_triggered(self, setup_id: str, session_id: str) -> ActiveSetup:
        """Remove and return an active setup once it has triggered."""
        self._validate_identity(setup_id, session_id)
        key = (session_id, setup_id)
        with self._lock:
            setup = self._active.pop(key, None)
            if setup is None:
                raise KeyError("ACTIVE_SETUP_NOT_FOUND")
            return setup

    def get_active(self, setup_id: str, session_id: str) -> ActiveSetup | None:
        self._validate_identity(setup_id, session_id)
        with self._lock:
            return self._active.get((session_id, setup_id))

    def active_setups(self, session_id: str | None = None) -> tuple[ActiveSetup, ...]:
        with self._lock:
            items = (
                setup for setup in self._active.values()
                if session_id is None or setup.session_id == session_id
            )
            return tuple(sorted(items, key=lambda item: (item.session_id, item.created_bar_index, item.setup_id)))
