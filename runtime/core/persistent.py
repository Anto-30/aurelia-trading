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
                resolution_evidence_id=item.get("resolution_evidence_id"),
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
            updated = IntentRecord(
                intent_id, txid, current.economic_effect_count, False,
                current.resolution_evidence_id,
            )
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
                None,
            )
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

        This mutates durable state but does not verify the evidence itself. Only
        the controlled recovery path may call it with a verified evidence ID.
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
        """Return every persisted intent whose broker outcome still needs recovery."""
        with self._lock:
            return tuple(sorted(
                intent_id
                for intent_id, record in self._records.items()
                if record.broker_outcome_unknown and not record.broker_transaction_id
            ))

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


# Identity binding delegates to a pre-existing durable AURELIA store.
# This adapter intentionally has no cache or default in-memory fallback.
from typing import Protocol, runtime_checkable
from .models import CompositeAccountIdentity


@runtime_checkable
class ExistingAccountBindingStore(Protocol):
    """Required contract for an AURELIA-owned durable account-binding store."""

    def bind_account(self, identity: CompositeAccountIdentity) -> None: ...

    def get_binding_by_aurelia_uuid(
        self, aurelia_uuid: str
    ) -> CompositeAccountIdentity | None: ...

    def get_binding_by_deriv_loginid(
        self, deriv_loginid: str
    ) -> CompositeAccountIdentity | None: ...


class BrokerUUIDToLoginBinding:
    """Bind the composite broker identity through an injected existing store.

    No persistence is implemented here. Durability, encryption, locking and
    restart recovery remain the responsibility of the injected store. Missing
    persistence capability is a construction-time error, not a silent cache.
    """

    def __init__(self, existing_binding_store: ExistingAccountBindingStore):
        if existing_binding_store is None:
            raise ValueError("EXISTING_ACCOUNT_BINDING_STORE_REQUIRED")
        required_methods = (
            "bind_account",
            "get_binding_by_aurelia_uuid",
            "get_binding_by_deriv_loginid",
        )
        if any(not callable(getattr(existing_binding_store, name, None)) for name in required_methods):
            raise TypeError("EXISTING_ACCOUNT_BINDING_STORE_INTERFACE_INVALID")
        self.existing_store = existing_binding_store

    def bind_complete_identity(self, identity: CompositeAccountIdentity) -> None:
        if not isinstance(identity, CompositeAccountIdentity) or identity.validate_integrity() is not True:
            raise ValueError("IDENTITY_INTEGRITY_VALIDATION_FAILED")
        self.existing_store.bind_account(identity)

    def get_binding_by_aurelia_uuid(
        self, aurelia_uuid: str
    ) -> CompositeAccountIdentity | None:
        identity = self.existing_store.get_binding_by_aurelia_uuid(aurelia_uuid)
        if identity is None:
            return None
        if not isinstance(identity, CompositeAccountIdentity) or identity.validate_integrity() is not True:
            raise ValueError("STORED_IDENTITY_INTEGRITY_VALIDATION_FAILED")
        if identity.aurelia.internal_uuid != aurelia_uuid:
            raise ValueError("STORED_AURELIA_IDENTITY_KEY_MISMATCH")
        return identity

    def get_binding_by_deriv_loginid(
        self, deriv_loginid: str
    ) -> CompositeAccountIdentity | None:
        identity = self.existing_store.get_binding_by_deriv_loginid(deriv_loginid)
        if identity is None:
            return None
        if not isinstance(identity, CompositeAccountIdentity) or identity.validate_integrity() is not True:
            raise ValueError("STORED_IDENTITY_INTEGRITY_VALIDATION_FAILED")
        if identity.deriv_account.deriv_loginid != deriv_loginid:
            raise ValueError("STORED_DERIV_LOGINID_KEY_MISMATCH")
        return identity


    def _delegate_oauth_store(self, method_name: str, **kwargs):
        method = getattr(self.existing_store, method_name, None)
        if not callable(method):
            raise TypeError("ENCRYPTED_OAUTH_BINDING_STORE_INTERFACE_REQUIRED")
        return method(**kwargs)

    def create_pending_oauth_authorization(self, **kwargs):
        return self._delegate_oauth_store("create_pending_oauth_authorization", **kwargs)

    def consume_pending_oauth_authorization(self, **kwargs):
        return self._delegate_oauth_store("consume_pending_oauth_authorization", **kwargs)

    def store_oauth_access_token(self, **kwargs):
        return self._delegate_oauth_store("store_oauth_access_token", **kwargs)

    def get_oauth_access_token(self, **kwargs):
        return self._delegate_oauth_store("get_oauth_access_token", **kwargs)

    def delete_oauth_access_token(self, **kwargs):
        return self._delegate_oauth_store("delete_oauth_access_token", **kwargs)

    def validate_binding_integrity(self, aurelia_uuid: str) -> bool:
        identity = self.get_binding_by_aurelia_uuid(aurelia_uuid)
        return identity is not None and identity.validate_integrity() is True
