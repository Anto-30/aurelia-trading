from __future__ import annotations

import json
import math
import os
import re
import tempfile
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from .fencing import FenceToken
from .idempotency import IntentRecord
from .models import AccountIdentity, LedgerEvent


class _AtomicWriteDurabilityError(OSError):
    """The replacement happened, but parent-directory durability is unknown."""


def _atomic_write(path: Path, payload: str) -> None:
    """Replace a state file and distinguish pre-commit from ambiguous failures."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    replaced = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        replaced = True
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError as exc:
            # The target path may already expose the new payload. Reporting a
            # normal write failure would invite a retry against stale memory.
            raise _AtomicWriteDurabilityError(
                "PERSISTENT_DIRECTORY_FSYNC_FAILED_AFTER_REPLACE"
            ) from exc
    except OSError:
        if not replaced:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


class PersistentIdempotencyStore:
    """Restart-safe idempotency state with strict loading and atomic updates.

    Malformed, partial, contradictory, or unsupported persisted state is a
    startup failure. It is never interpreted as an empty store because that
    could permit a duplicate economic effect after restart.
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._poisoned = False
        self._records: dict[str, IntentRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("IDEMPOTENCY_STORE_CORRUPT") from exc
        if (
            not isinstance(payload, dict)
            or isinstance(payload.get("version"), bool)
            or not isinstance(payload.get("version"), int)
            or payload.get("version") != self.SCHEMA_VERSION
            or not isinstance(payload.get("records"), list)
        ):
            raise RuntimeError("IDEMPOTENCY_STORE_SCHEMA_INVALID")

        loaded: dict[str, IntentRecord] = {}
        for item in payload["records"]:
            if not isinstance(item, dict):
                raise RuntimeError("IDEMPOTENCY_STORE_RECORD_INVALID")
            intent_id = item.get("intent_id")
            transaction_id = item.get("broker_transaction_id")
            effect_count = item.get("economic_effect_count", 0)
            outcome_unknown = item.get("broker_outcome_unknown", False)
            resolution_id = item.get("resolution_evidence_id")

            if not _non_empty_string(intent_id):
                raise RuntimeError("IDEMPOTENCY_STORE_INTENT_ID_INVALID")
            intent_id = intent_id.strip()
            if intent_id in loaded:
                raise RuntimeError("IDEMPOTENCY_STORE_DUPLICATE_INTENT")
            if transaction_id is not None and not _non_empty_string(transaction_id):
                raise RuntimeError("IDEMPOTENCY_STORE_TRANSACTION_ID_INVALID")
            if (
                isinstance(effect_count, bool)
                or not isinstance(effect_count, int)
                or effect_count not in (0, 1)
            ):
                raise RuntimeError("IDEMPOTENCY_STORE_EFFECT_COUNT_INVALID")
            if not isinstance(outcome_unknown, bool):
                raise RuntimeError("IDEMPOTENCY_STORE_UNKNOWN_FLAG_INVALID")
            if resolution_id is not None and not _non_empty_string(resolution_id):
                raise RuntimeError("IDEMPOTENCY_STORE_RESOLUTION_ID_INVALID")
            if outcome_unknown and (transaction_id is not None or resolution_id is not None):
                raise RuntimeError("IDEMPOTENCY_STORE_UNKNOWN_STATE_CONTRADICTORY")

            loaded[intent_id] = IntentRecord(
                intent_id=intent_id,
                broker_transaction_id=transaction_id.strip() if transaction_id else None,
                economic_effect_count=effect_count,
                broker_outcome_unknown=outcome_unknown,
                resolution_evidence_id=resolution_id.strip() if resolution_id else None,
            )
        self._records = loaded

    def _commit(self, candidate: dict[str, IntentRecord]) -> None:
        if self._poisoned:
            raise RuntimeError("IDEMPOTENCY_STORE_POISONED")
        payload = {
            "version": self.SCHEMA_VERSION,
            "records": [asdict(record) for record in candidate.values()],
        }
        try:
            _atomic_write(
                self.path,
                json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
            )
        except _AtomicWriteDurabilityError as exc:
            self._poisoned = True
            raise RuntimeError(
                "IDEMPOTENCY_STORE_DURABILITY_UNCERTAIN_STORE_POISONED"
            ) from exc
        except (OSError, TypeError, ValueError) as exc:
            raise RuntimeError("IDEMPOTENCY_STORE_PERSISTENCE_FAILED") from exc
        self._records = candidate

    def get(self, intent_id: str) -> IntentRecord | None:
        with self._lock:
            return self._records.get(intent_id)

    def register_intent(self, intent_id: str) -> IntentRecord:
        if not _non_empty_string(intent_id):
            raise ValueError("INTENT_ID_REQUIRED")
        normalized = intent_id.strip()
        with self._lock:
            existing = self._records.get(normalized)
            if existing is not None:
                return existing
            candidate = dict(self._records)
            record = IntentRecord(normalized, None, 0)
            candidate[normalized] = record
            self._commit(candidate)
            return record

    def attach_broker_transaction(self, intent_id: str, txid: str) -> IntentRecord:
        if not _non_empty_string(txid):
            raise ValueError("BROKER_TRANSACTION_ID_REQUIRED")
        with self._lock:
            current = self._records.get(intent_id)
            if current is None:
                raise KeyError(intent_id)
            if current.broker_outcome_unknown:
                raise RuntimeError("UNKNOWN_OUTCOME_REQUIRES_VERIFIED_RECOVERY")
            if current.broker_transaction_id and current.broker_transaction_id != txid:
                raise RuntimeError("BROKER_TRANSACTION_CONFLICT")
            updated = IntentRecord(
                intent_id=intent_id,
                broker_transaction_id=txid.strip(),
                economic_effect_count=current.economic_effect_count,
                broker_outcome_unknown=False,
                resolution_evidence_id=current.resolution_evidence_id,
            )
            candidate = dict(self._records)
            candidate[intent_id] = updated
            self._commit(candidate)
            return updated

    def record_unknown_outcome(self, intent_id: str) -> IntentRecord:
        with self._lock:
            current = self._records.get(intent_id)
            if current is None:
                raise KeyError(intent_id)
            if current.broker_transaction_id:
                return current
            if current.broker_outcome_unknown:
                return current
            updated = IntentRecord(
                intent_id=intent_id,
                broker_transaction_id=None,
                economic_effect_count=current.economic_effect_count,
                broker_outcome_unknown=True,
                resolution_evidence_id=None,
            )
            candidate = dict(self._records)
            candidate[intent_id] = updated
            self._commit(candidate)
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
        """Resolve UNKNOWN only with externally verified recovery evidence.

        This store checks caller assertions and evidence ID shape; it does not
        contact a broker or independently certify the evidence.
        """
        if broker_state_known is not True or reconciliation_healthy is not True:
            raise RuntimeError("UNKNOWN_OUTCOME_RECOVERY_EVIDENCE_INCOMPLETE")
        if not isinstance(economic_effect_confirmed, bool):
            raise ValueError("ECONOMIC_EFFECT_CONFIRMATION_MUST_BE_BOOLEAN")
        if not _non_empty_string(resolution_evidence_id):
            raise ValueError("RECOVERY_EVIDENCE_ID_REQUIRED")
        txid = broker_transaction_id.strip() if _non_empty_string(broker_transaction_id) else None
        if economic_effect_confirmed and txid is None:
            raise ValueError("CONFIRMED_ECONOMIC_EFFECT_REQUIRES_TRANSACTION_ID")
        if not economic_effect_confirmed and txid is not None:
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
                resolution_evidence_id=resolution_evidence_id.strip(),
            )
            candidate = dict(self._records)
            candidate[intent_id] = updated
            self._commit(candidate)
            return updated

    def unresolved_unknown_intents(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(
                intent_id
                for intent_id, record in self._records.items()
                if record.broker_outcome_unknown and not record.broker_transaction_id
            ))

    def record_economic_effect(self, intent_id: str) -> IntentRecord:
        with self._lock:
            current = self._records.get(intent_id)
            if current is None:
                raise KeyError(intent_id)
            if current.broker_outcome_unknown:
                raise RuntimeError("UNKNOWN_OUTCOME_REQUIRES_VERIFIED_RECOVERY")
            if current.economic_effect_count >= 1:
                raise RuntimeError("DUPLICATE_ECONOMIC_EFFECT")
            updated = IntentRecord(
                intent_id=intent_id,
                broker_transaction_id=current.broker_transaction_id,
                economic_effect_count=1,
                broker_outcome_unknown=False,
                resolution_evidence_id=current.resolution_evidence_id,
            )
            candidate = dict(self._records)
            candidate[intent_id] = updated
            self._commit(candidate)
            return updated


class PersistentExecutionFence:
    """Durable generation fence for one active local executor.

    Malformed generation data invalidates the fence and never resets to zero.
    This file is not a distributed lease: multi-replica execution still
    requires a transactional external fencing service.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._poisoned = False
        self._generation = self._read_generation()

    def _read_generation(self) -> int:
        if not self.path.exists():
            return 0
        try:
            raw = self.path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError) as exc:
            raise RuntimeError("EXECUTION_FENCE_STATE_UNREADABLE") from exc
        if not re.fullmatch(r"[1-9][0-9]*", raw):
            raise RuntimeError("EXECUTION_FENCE_STATE_CORRUPT")
        try:
            generation = int(raw)
        except ValueError as exc:
            raise RuntimeError("EXECUTION_FENCE_STATE_CORRUPT") from exc
        if generation < 1:
            raise RuntimeError("EXECUTION_FENCE_STATE_CORRUPT")
        return generation

    def _write_generation(self, generation: int) -> None:
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise ValueError("EXECUTION_FENCE_GENERATION_INVALID")
        if self._poisoned:
            raise RuntimeError("EXECUTION_FENCE_STORE_POISONED")
        try:
            _atomic_write(self.path, f"{generation}\n")
        except _AtomicWriteDurabilityError as exc:
            self._poisoned = True
            raise RuntimeError(
                "EXECUTION_FENCE_DURABILITY_UNCERTAIN_STORE_POISONED"
            ) from exc
        except OSError as exc:
            raise RuntimeError("EXECUTION_FENCE_PERSISTENCE_FAILED") from exc

    def acquire(self, owner: str) -> FenceToken:
        if not _non_empty_string(owner):
            raise ValueError("EXECUTION_FENCE_OWNER_REQUIRED")
        with self._lock:
            generation = max(self._generation, self._read_generation()) + 1
            self._write_generation(generation)
            self._generation = generation
            return FenceToken(generation, owner.strip())

    def valid(self, token: FenceToken) -> bool:
        if self._poisoned:
            return False
        if (
            not isinstance(token, FenceToken)
            or isinstance(token.generation, bool)
            or not isinstance(token.generation, int)
            or token.generation < 1
            or not _non_empty_string(token.owner)
        ):
            return False
        with self._lock:
            try:
                generation = self._read_generation()
            except (OSError, RuntimeError):
                return False
            return token.generation == self._generation == generation

    def revoke(self) -> int:
        with self._lock:
            generation = max(self._generation, self._read_generation()) + 1
            self._write_generation(generation)
            self._generation = generation
            return generation


class PersistentLedger:
    """Restart-safe append ledger with strict schema and atomic commits."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._poisoned = False
        self._events: dict[str, LedgerEvent] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("PERSISTENT_LEDGER_CORRUPT") from exc
        if (
            not isinstance(payload, dict)
            or isinstance(payload.get("version"), bool)
            or not isinstance(payload.get("version"), int)
            or payload.get("version") != self.SCHEMA_VERSION
            or not isinstance(payload.get("events"), list)
        ):
            raise RuntimeError("PERSISTENT_LEDGER_SCHEMA_INVALID")

        loaded: dict[str, LedgerEvent] = {}
        for item in payload["events"]:
            if not isinstance(item, dict):
                raise RuntimeError("PERSISTENT_LEDGER_EVENT_INVALID")
            try:
                event_id = item["event_id"]
                intent_id = item["intent_id"]
                account_data = item["account"]
                event_type = item["event_type"]
                amount_raw = item["amount"]
                currency = item["currency"]
                occurred_at_raw = item["occurred_at"]
                metadata = item.get("metadata", {})
                transaction_id = item.get("broker_transaction_id")
                if not all(_non_empty_string(value) for value in (
                    event_id, intent_id, event_type, currency
                )):
                    raise ValueError("blank required field")
                event_id = event_id.strip()
                intent_id = intent_id.strip()
                if event_id in loaded:
                    raise ValueError("duplicate event ID")
                if not isinstance(account_data, dict):
                    raise ValueError("account must be an object")
                account = AccountIdentity(**account_data)
                if not isinstance(amount_raw, (int, float)) or isinstance(amount_raw, bool):
                    raise ValueError("amount must be numeric")
                amount = float(amount_raw)
                if not math.isfinite(amount):
                    raise ValueError("amount must be finite")
                occurred_at = datetime.fromisoformat(str(occurred_at_raw))
                if occurred_at.tzinfo is None:
                    raise ValueError("event time must be timezone-aware")
                if not isinstance(metadata, dict):
                    raise ValueError("metadata must be an object")
                if transaction_id is not None and not _non_empty_string(transaction_id):
                    raise ValueError("transaction ID must be non-empty or null")
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError("PERSISTENT_LEDGER_EVENT_INVALID") from exc

            loaded[event_id] = LedgerEvent(
                event_id=event_id,
                intent_id=intent_id,
                account=account,
                event_type=event_type.strip(),
                amount=amount,
                currency=currency.strip().upper(),
                occurred_at=occurred_at,
                broker_transaction_id=transaction_id.strip() if transaction_id else None,
                metadata=metadata,
            )
        self._events = loaded

    def _commit(self, candidate: dict[str, LedgerEvent]) -> None:
        if self._poisoned:
            raise RuntimeError("PERSISTENT_LEDGER_STORE_POISONED")
        payload = {
            "version": self.SCHEMA_VERSION,
            "events": [asdict(event) for event in candidate.values()],
        }
        try:
            serialized = json.dumps(payload, sort_keys=True, default=str, allow_nan=False) + "\n"
            _atomic_write(self.path, serialized)
        except _AtomicWriteDurabilityError as exc:
            self._poisoned = True
            raise RuntimeError(
                "PERSISTENT_LEDGER_DURABILITY_UNCERTAIN_STORE_POISONED"
            ) from exc
        except (OSError, TypeError, ValueError) as exc:
            raise RuntimeError("PERSISTENT_LEDGER_PERSISTENCE_FAILED") from exc
        self._events = candidate

    def post(self, event: LedgerEvent) -> bool:
        if not isinstance(event, LedgerEvent) or not all(_non_empty_string(value) for value in (
            event.event_id, event.intent_id, event.event_type, event.currency
        )):
            raise ValueError("LEDGER_EVENT_INVALID")
        if not isinstance(event.account, AccountIdentity):
            raise ValueError("LEDGER_EVENT_ACCOUNT_INVALID")
        if not isinstance(event.occurred_at, datetime) or event.occurred_at.tzinfo is None:
            raise ValueError("LEDGER_EVENT_TIMEZONE_INVALID")
        if (
            isinstance(event.amount, bool)
            or not isinstance(event.amount, (int, float))
            or not math.isfinite(float(event.amount))
        ):
            raise ValueError("LEDGER_EVENT_AMOUNT_INVALID")
        if not isinstance(event.metadata, Mapping):
            raise ValueError("LEDGER_EVENT_METADATA_INVALID")
        if event.broker_transaction_id is not None and not _non_empty_string(
            event.broker_transaction_id
        ):
            raise ValueError("LEDGER_EVENT_TRANSACTION_ID_INVALID")
        try:
            metadata = deepcopy(dict(event.metadata))
            # Reject metadata that cannot be represented by the persisted JSON
            # contract; do not stringify arbitrary objects into audit evidence.
            json.dumps(metadata, allow_nan=False)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("LEDGER_EVENT_METADATA_INVALID") from exc

        normalized = LedgerEvent(
            event_id=event.event_id.strip(),
            intent_id=event.intent_id.strip(),
            account=event.account,
            event_type=event.event_type.strip(),
            amount=float(event.amount),
            currency=event.currency.strip().upper(),
            occurred_at=event.occurred_at,
            broker_transaction_id=(
                event.broker_transaction_id.strip()
                if event.broker_transaction_id is not None
                else None
            ),
            metadata=metadata,
        )
        with self._lock:
            if self._poisoned:
                raise RuntimeError("PERSISTENT_LEDGER_STORE_POISONED")
            if normalized.event_id in self._events:
                return False
            candidate = dict(self._events)
            candidate[normalized.event_id] = normalized
            self._commit(candidate)
            return True

    def events(self) -> list[LedgerEvent]:
        with self._lock:
            return [
                replace(event, metadata=deepcopy(dict(event.metadata)))
                for event in self._events.values()
            ]
