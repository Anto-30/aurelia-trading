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
    resolution_evidence_id: str | None = None


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
                resolution_evidence_id=value.get("resolution_evidence_id"),
            )
            if record.economic_effect_count < 0 or record.economic_effect_count > 1:
                raise RuntimeError("IDEMPOTENCY_STORE_INVALID_EFFECT_COUNT")
            self._records[record.intent_id] = record

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        # Snapshot is atomically replaced after every state transition. Keep
        # key order deterministic, but avoid pretty-printing the growing registry
        # on every write: the full 3,600-cycle control-path exercise otherwise
        # spends most of its time serializing whitespace and rewriting bytes.
        tmp.write_text(
            json.dumps(
                {k: asdict(v) for k, v in self._records.items()},
                sort_keys=True,
                separators=(",", ":"),
            ) + "\n",
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
            updated = IntentRecord(
                intent_id, transaction_id, current.economic_effect_count, False,
                current.resolution_evidence_id,
            )
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
            updated = IntentRecord(
                intent_id, current.broker_transaction_id, 1,
                current.broker_outcome_unknown, current.resolution_evidence_id,
            )
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
            updated = IntentRecord(intent_id, None, current.economic_effect_count, True, None)
            self._records[intent_id] = updated
            self._save()
            return updated

    def resolve_unknown_outcome(
        self,
        intent_id: str,
        *,
        broker_state_known: bool,
        reconciliation_healthy: bool,
        economic_effect_confirmed: bool,
        broker_transaction_id: str | None,
        resolution_evidence_id: str,
    ) -> IntentRecord:
        """Resolve UNKNOWN only after authenticated broker lookup and reconciliation.

        The caller must supply the evidence record generated by the recovery
        workflow. This storage method never queries a broker and does not itself
        certify the evidence.
        """
        if broker_state_known is not True or reconciliation_healthy is not True:
            raise RuntimeError("UNKNOWN_OUTCOME_RECOVERY_EVIDENCE_INCOMPLETE")
        if not isinstance(economic_effect_confirmed, bool):
            raise ValueError("ECONOMIC_EFFECT_CONFIRMATION_MUST_BE_BOOLEAN")
        evidence_id = str(resolution_evidence_id or "").strip()
        txid = str(broker_transaction_id or "").strip() or None
        if not evidence_id:
            raise ValueError("RECOVERY_EVIDENCE_ID_REQUIRED")
        if economic_effect_confirmed and not txid:
            raise ValueError("CONFIRMED_ECONOMIC_EFFECT_REQUIRES_TRANSACTION_ID")
        if not economic_effect_confirmed and txid:
            raise ValueError("NO_EFFECT_RESOLUTION_CANNOT_INCLUDE_TRANSACTION_ID")
        with self._lock:
            current = self._records.get(intent_id)
            if current is None or not current.broker_outcome_unknown:
                raise RuntimeError("UNKNOWN_OUTCOME_RECORD_NOT_FOUND")
            updated = IntentRecord(
                intent_id=intent_id,
                broker_transaction_id=txid,
                economic_effect_count=1 if economic_effect_confirmed else 0,
                broker_outcome_unknown=False,
                resolution_evidence_id=evidence_id,
            )
            self._records[intent_id] = updated
            self._save()
            return updated

    def unresolved_unknown_intents(self) -> tuple[str, ...]:
        """Return every durable intent whose broker outcome still needs recovery."""
        with self._lock:
            return tuple(sorted(
                intent_id
                for intent_id, record in self._records.items()
                if record.broker_outcome_unknown and not record.broker_transaction_id
            ))

    def economic_effect_count(self, intent_id):
        current = self.get(intent_id)
        return 0 if current is None else current.economic_effect_count
