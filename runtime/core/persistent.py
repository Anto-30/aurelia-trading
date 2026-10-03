from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock

from .fencing import FenceToken
from .idempotency import IntentRecord


class PersistentIdempotencyStore:
    '''Restart-safe idempotency state for a single durable writer.'''

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._records: dict[str, IntentRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for item in data.get("records", []):
            record = IntentRecord(
                item["intent_id"],
                item.get("broker_transaction_id"),
                int(item.get("economic_effect_count", 0)),
            )
            self._records[record.intent_id] = record

    def _save(self) -> None:
        payload = {"version": 1, "records": [asdict(x) for x in self._records.values()]}
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)

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
            updated = IntentRecord(intent_id, txid, current.economic_effect_count)
            self._records[intent_id] = updated
            self._save()
            return updated

    def record_economic_effect(self, intent_id: str) -> IntentRecord:
        with self._lock:
            current = self._records[intent_id]
            if current.economic_effect_count >= 1:
                raise RuntimeError("DUPLICATE_ECONOMIC_EFFECT")
            updated = IntentRecord(intent_id, current.broker_transaction_id, 1)
            self._records[intent_id] = updated
            self._save()
            return updated

    def get(self, intent_id: str) -> IntentRecord | None:
        with self._lock:
            return self._records.get(intent_id)


class PersistentExecutionFence:
    '''Restart-aware fence for a single durable writer.

    Multi-replica production must replace this file primitive with an
    external transactional lease/fencing service; the runtime never assumes
    local files are sufficient for a distributed cluster.
    '''

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
