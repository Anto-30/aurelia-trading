from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock


@dataclass(frozen=True)
class IntentRecord:
    intent_id: str
    broker_transaction_id: str | None
    economic_effect_count: int
    broker_outcome_unknown: bool = False


class IdempotencyStore:
    """Durable intent/economic-effect registry.

    A process restart must not erase knowledge of an accepted or unknown
    broker outcome. Persistence failures are fail-closed rather than ignored.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.getenv("AURELIA_IDEMPOTENCY_PATH", "data/runtime/idempotency.json"))
        self._records: dict[str, IntentRecord] = {}
        self._lock = Lock()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise RuntimeError("IDEMPOTENCY_STORE_CORRUPT")
        for intent_id, value in raw.items():
            if not isinstance(value, dict):
                raise RuntimeError("IDEMPOTENCY_STORE_CORRUPT")
            record = IntentRecord(
                intent_id=str(value.get("intent_id") or intent_id),
                broker_transaction_id=(
                    str(value["broker_transaction_id"])
                    if value.get("broker_transaction_id") is not None
                    else None
                ),
                economic_effect_count=int(value.get("economic_effect_count", 0)),
                broker_outcome_unknown=bool(value.get("broker_outcome_unknown", False)),
            )
            if record.economic_effect_count < 0 or record.economic_effect_count > 1:
                raise RuntimeError("IDEMPOTENCY_STORE_INVALID_EFFECT_COUNT")
            self._records[record.intent_id] = record

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps({k: asdict(v) for k, v in self._records.items()}, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    def get(self, intent_id):
        with self._lock:
            return self._records.get(intent_id)

    def register_intent(self, intent_id):
        with self._lock:
            if intent_id in self._records:
                return self._records[intent_id]
            self._records[intent_id] = IntentRecord(intent_id, None, 0)
            self._save()
            return self._records[intent_id]

    def attach_broker_transaction(self, intent_id, transaction_id):
        with self._lock:
            current = self._records.get(intent_id)
            if current is None:
                raise KeyError(intent_id)
            if current.broker_transaction_id and current.broker_transaction_id != transaction_id:
                raise RuntimeError("BROKER_TRANSACTION_CONFLICT")
            updated = IntentRecord(intent_id, transaction_id, current.economic_effect_count, False)
            self._records[intent_id] = updated
            self._save()
            return updated

    def record_economic_effect(self, intent_id):
        with self._lock:
            current = self._records.get(intent_id)
            if current is None:
                raise KeyError(intent_id)
            if current.economic_effect_count >= 1:
                raise RuntimeError("DUPLICATE_ECONOMIC_EFFECT")
            updated = IntentRecord(intent_id, current.broker_transaction_id, 1, current.broker_outcome_unknown)
            self._records[intent_id] = updated
            self._save()
            return updated

    def record_unknown_outcome(self, intent_id):
        with self._lock:
            current = self._records.get(intent_id)
            if current is None:
                raise KeyError(intent_id)
            if current.broker_transaction_id:
                return current
            updated = IntentRecord(intent_id, None, current.economic_effect_count, True)
            self._records[intent_id] = updated
            self._save()
            return updated

    def economic_effect_count(self, intent_id):
        current = self.get(intent_id)
        return 0 if current is None else current.economic_effect_count
