from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from threading import Lock

from .fencing import FenceToken
from .idempotency import IntentRecord
from .models import LedgerEvent


class PersistentIdempotencyStore:
    """Restart-safe idempotency state."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._records: dict[str, IntentRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        for item in payload.get("records", []):
            record = IntentRecord(
                intent_id=item["intent_id"],
                broker_transaction_id=item.get("broker_transaction_id"),
                economic_effect_count=int(item.get("economic_effect_count", 0)),
                broker_outcome_unknown=bool(item.get("broker_outcome_unknown", False)),
            )
            self._records[record.intent_id] = record

    def _save(self) -> None:
        payload = {"version": 1, "records": [asdict(x) for x in self._records.values()]}
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temp.replace(self.path)

    def get(self, intent_id: str) -> IntentRecord | None:
        with self._lock:
            return self._records.get(intent_id)

    def register_intent(self, intent_id: str) -> IntentRecord:
        with self._lock:
            existing = self._records.get(intent_id)
            if existing:
                return existing
            record = IntentRecord(intent_id, None, 0)
            self._records[intent_id] = record
            self._save()
            return record

    def attach_broker_transaction(self, intent_id: str, txid: str) -> IntentRecord:
        with self._lock:
            current = self._records[intent_id]
            if current.broker_transaction_id and current.broker_transaction_id != txid:
                raise RuntimeError("BROKER_TRANSACTION_CONFLICT")
            updated = IntentRecord(intent_id, txid, current.economic_effect_count, False)
            self._records[intent_id] = updated
            self._save()
            return updated

    def record_unknown_outcome(self, intent_id: str) -> IntentRecord:
        with self._lock:
            current = self._records[intent_id]
            if current.broker_transaction_id:
                return current
            updated = IntentRecord(
                intent_id,
                None,
                current.economic_effect_count,
                True,
            )
            self._records[intent_id] = updated
            self._save()
            return updated

    def record_economic_effect(self, intent_id: str) -> IntentRecord:
        with self._lock:
            current = self._records[intent_id]
            if current.economic_effect_count >= 1:
                raise RuntimeError("DUPLICATE_ECONOMIC_EFFECT")
            updated = IntentRecord(
                intent_id,
                current.broker_transaction_id,
                1,
                current.broker_outcome_unknown,
            )
            self._records[intent_id] = updated
            self._save()
            return updated


class PersistentExecutionFence:
    """Durable generation fence for a single active executor.

    Multi-replica production still requires an external transactional lease or
    fencing service. A local file is intentionally not treated as sufficient
    for distributed execution.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._generation = self._read_generation()

    def _read_generation(self) -> int:
        if not self.path.exists():
            return 0
        try:
            return int(self.path.read_text(encoding="utf-8").strip())
        except ValueError:
            return 0

    def acquire(self, owner: str) -> FenceToken:
        with self._lock:
            self._generation = max(self._generation, self._read_generation()) + 1
            self.path.write_text(str(self._generation), encoding="utf-8")
            return FenceToken(self._generation, owner)

    def valid(self, token: FenceToken) -> bool:
        with self._lock:
            return token.generation == self._generation and token.generation == self._read_generation()

    def revoke(self) -> int:
        with self._lock:
            self._generation = max(self._generation, self._read_generation()) + 1
            self.path.write_text(str(self._generation), encoding="utf-8")
            return self._generation


class PersistentLedger:
    """Restart-safe append ledger backed by an atomic JSON replace."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._events: dict[str, LedgerEvent] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        for item in payload.get("events", []):
            account = item["account"]
            from .models import AccountIdentity
            self._events[item["event_id"]] = LedgerEvent(
                event_id=item["event_id"],
                intent_id=item["intent_id"],
                account=AccountIdentity(**account),
                event_type=item["event_type"],
                amount=float(item["amount"]),
                currency=item["currency"],
                occurred_at=__import__("datetime").datetime.fromisoformat(item["occurred_at"]),
                broker_transaction_id=item.get("broker_transaction_id"),
                metadata=item.get("metadata", {}),
            )

    def _save(self) -> None:
        payload = {"version": 1, "events": [asdict(x) for x in self._events.values()]}
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, sort_keys=True, default=str), encoding="utf-8")
        temp.replace(self.path)

    def post(self, event: LedgerEvent) -> bool:
        with self._lock:
            if event.event_id in self._events:
                return False
            self._events[event.event_id] = event
            self._save()
            return True

    def events(self) -> list[LedgerEvent]:
        with self._lock:
            return list(self._events.values())
