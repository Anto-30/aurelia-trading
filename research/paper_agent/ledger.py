"""Append-only SQLite event ledger for the research-only paper decision gate."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_ALLOWED_EVENTS = frozenset({
    "DECISION_EVALUATED", "PAPER_INTENT", "MISSED_SIGNAL",
    "KILL_SWITCH_TRIPPED", "KILL_SWITCH_RESET", "SYSTEM_ALERT",
})


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class PaperEventLedger:
    """Writes a verifiable hash chain; duplicate IDs are idempotent.

    This ledger records decisions/intents/misses only. Since this package never
    places or simulates broker orders, it does not fabricate fills or PnL.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS paper_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                occurred_at_utc TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL
            )
        """)
        self._db.executescript("""
            CREATE TRIGGER IF NOT EXISTS paper_events_no_update
            BEFORE UPDATE ON paper_events BEGIN
                SELECT RAISE(ABORT, 'PAPER_LEDGER_APPEND_ONLY');
            END;
            CREATE TRIGGER IF NOT EXISTS paper_events_no_delete
            BEFORE DELETE ON paper_events BEGIN
                SELECT RAISE(ABORT, 'PAPER_LEDGER_APPEND_ONLY');
            END;
        """)

    def append(
        self, *, event_id: str, event_type: str, payload: Mapping[str, Any],
        occurred_at_utc: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 256:
            raise ValueError("PAPER_EVENT_ID_INVALID")
        if event_type not in _ALLOWED_EVENTS:
            raise ValueError("PAPER_EVENT_TYPE_INVALID")
        if not isinstance(payload, Mapping):
            raise ValueError("PAPER_EVENT_PAYLOAD_INVALID")
        payload_json = _canonical(dict(payload))
        payload_hash = _sha256(payload_json)
        timestamp = occurred_at_utc or datetime.now(timezone.utc).isoformat()
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("PAPER_EVENT_TIMESTAMP_INVALID") from exc
        if parsed.tzinfo is None:
            raise ValueError("PAPER_EVENT_TIMESTAMP_MUST_BE_TIMEZONE_AWARE")

        # Serialize the read/allocate/hash/insert sequence so simultaneous
        # writers cannot create duplicate sequence numbers or forks.
        self._db.execute("BEGIN IMMEDIATE")
        try:
            existing = self._db.execute(
                "SELECT * FROM paper_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            if existing is not None:
                if existing["event_type"] != event_type or existing["payload_json"] != payload_json:
                    raise ValueError("PAPER_EVENT_ID_CONFLICT")
                self._db.execute("COMMIT")
                return dict(existing)

            prior = self._db.execute(
                "SELECT event_hash FROM paper_events ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous_hash = prior["event_hash"] if prior else "GENESIS"
            sequence = int(self._db.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM paper_events"
            ).fetchone()["next_sequence"])
            event_body = {
                "sequence": sequence, "event_id": event_id,
                "occurred_at_utc": timestamp, "event_type": event_type,
                "payload_sha256": payload_hash, "previous_hash": previous_hash,
            }
            event_hash = _sha256(_canonical(event_body))
            self._db.execute(
                """INSERT INTO paper_events
                   (sequence, event_id, occurred_at_utc, event_type, payload_json,
                    payload_sha256, previous_hash, event_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (sequence, event_id, timestamp, event_type, payload_json, payload_hash,
                 previous_hash, event_hash),
            )
            row = self._db.execute(
                "SELECT * FROM paper_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            self._db.execute("COMMIT")
            return dict(row)
        except Exception:
            if self._db.in_transaction:
                self._db.execute("ROLLBACK")
            raise

    def read_all(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM paper_events ORDER BY sequence ASC"
        ).fetchall()
        return [dict(row) for row in rows]

    def verify_chain(self) -> bool:
        expected_previous = "GENESIS"
        expected_sequence = 1
        for row in self.read_all():
            if int(row["sequence"]) != expected_sequence:
                return False
            payload_hash = _sha256(row["payload_json"])
            if payload_hash != row["payload_sha256"] or row["previous_hash"] != expected_previous:
                return False
            body = {
                "sequence": int(row["sequence"]), "event_id": row["event_id"],
                "occurred_at_utc": row["occurred_at_utc"], "event_type": row["event_type"],
                "payload_sha256": payload_hash, "previous_hash": expected_previous,
            }
            computed = _sha256(_canonical(body))
            if computed != row["event_hash"]:
                return False
            expected_previous = computed
            expected_sequence += 1
        return True

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "PaperEventLedger":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
