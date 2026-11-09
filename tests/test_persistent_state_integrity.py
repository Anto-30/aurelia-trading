from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from runtime.core.fencing import FenceToken
from runtime.core.models import AccountIdentity, LedgerEvent
from runtime.core.persistent import (
    PersistentExecutionFence,
    PersistentIdempotencyStore,
    PersistentLedger,
)


class PersistentStateIntegrityTests(unittest.TestCase):
    def test_corrupt_fence_generation_blocks_instead_of_resetting_to_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fence.generation"
            path.write_text("not-a-generation\n", encoding="ascii")
            with self.assertRaisesRegex(RuntimeError, "EXECUTION_FENCE_STATE_CORRUPT"):
                PersistentExecutionFence(path)

    def test_fence_generation_is_monotonic_and_revocation_invalidates_old_token(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fence.generation"
            first = PersistentExecutionFence(path)
            token = first.acquire("executor-A")
            self.assertTrue(first.valid(token))

            revoked_generation = first.revoke()
            self.assertGreater(revoked_generation, token.generation)
            self.assertFalse(first.valid(token))

            restarted = PersistentExecutionFence(path)
            next_token = restarted.acquire("executor-B")
            self.assertGreater(next_token.generation, revoked_generation)
            self.assertTrue(restarted.valid(next_token))
            self.assertFalse(restarted.valid(token))

    def test_invalid_fence_token_is_never_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            fence = PersistentExecutionFence(Path(directory) / "fence.generation")
            self.assertFalse(fence.valid(FenceToken(0, "executor")))
            self.assertFalse(fence.valid(FenceToken(True, "executor")))
            self.assertFalse(fence.valid(FenceToken(1, "")))

    def test_idempotency_store_rejects_missing_schema_instead_of_empty_store(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "idempotency.json"
            path.write_text(json.dumps({"records": []}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "IDEMPOTENCY_STORE_SCHEMA_INVALID"):
                PersistentIdempotencyStore(path)

    def test_idempotency_store_rejects_contradictory_unknown_transaction_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "idempotency.json"
            path.write_text(
                json.dumps({
                    "version": 1,
                    "records": [{
                        "intent_id": "intent-1",
                        "broker_transaction_id": "tx-1",
                        "economic_effect_count": 0,
                        "broker_outcome_unknown": True,
                        "resolution_evidence_id": None,
                    }],
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError, "IDEMPOTENCY_STORE_UNKNOWN_STATE_CONTRADICTORY"
            ):
                PersistentIdempotencyStore(path)

    def test_unknown_outcome_survives_restart_and_requires_verified_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "idempotency.json"
            store = PersistentIdempotencyStore(path)
            store.register_intent("intent-1")
            store.record_unknown_outcome("intent-1")

            restarted = PersistentIdempotencyStore(path)
            self.assertEqual(restarted.unresolved_unknown_intents(), ("intent-1",))
            with self.assertRaisesRegex(
                RuntimeError, "UNKNOWN_OUTCOME_REQUIRES_VERIFIED_RECOVERY"
            ):
                restarted.attach_broker_transaction("intent-1", "tx-1")
            with self.assertRaisesRegex(
                RuntimeError, "UNKNOWN_OUTCOME_RECOVERY_EVIDENCE_INCOMPLETE"
            ):
                restarted.resolve_unknown_outcome(
                    "intent-1",
                    broker_state_known=False,
                    reconciliation_healthy=True,
                    economic_effect_confirmed=True,
                    broker_transaction_id="tx-1",
                    resolution_evidence_id="recovery-1",
                )

            resolved = restarted.resolve_unknown_outcome(
                "intent-1",
                broker_state_known=True,
                reconciliation_healthy=True,
                economic_effect_confirmed=True,
                broker_transaction_id="tx-1",
                resolution_evidence_id="recovery-1",
            )
            self.assertFalse(resolved.broker_outcome_unknown)
            self.assertEqual(resolved.economic_effect_count, 1)
            self.assertEqual(restarted.unresolved_unknown_intents(), ())
            with self.assertRaisesRegex(RuntimeError, "DUPLICATE_ECONOMIC_EFFECT"):
                restarted.record_economic_effect("intent-1")

            loaded_again = PersistentIdempotencyStore(path)
            record = loaded_again.get("intent-1")
            self.assertIsNotNone(record)
            self.assertEqual(record.broker_transaction_id, "tx-1")
            self.assertEqual(record.economic_effect_count, 1)
            self.assertEqual(record.resolution_evidence_id, "recovery-1")

    def test_failed_idempotency_write_does_not_commit_memory_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "idempotency.json"
            store = PersistentIdempotencyStore(path)
            with patch("runtime.core.persistent.os.replace", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(
                    RuntimeError, "IDEMPOTENCY_STORE_PERSISTENCE_FAILED"
                ):
                    store.register_intent("intent-not-durable")
            self.assertIsNone(store.get("intent-not-durable"))
            self.assertFalse(path.exists())

    def test_ledger_rejects_invalid_version_and_duplicate_event_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            path.write_text(json.dumps({"version": 2, "events": []}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "PERSISTENT_LEDGER_SCHEMA_INVALID"):
                PersistentLedger(path)

            duplicate_event = {
                "event_id": "event-1",
                "intent_id": "intent-1",
                "account": {
                    "loginid": "VRTC12345",
                    "account_type": "demo",
                    "currency": "USD",
                    "environment": "virtual",
                },
                "event_type": "INTENT_RESERVED",
                "amount": 1.0,
                "currency": "USD",
                "occurred_at": "2026-11-09T12:00:00+00:00",
                "broker_transaction_id": "tx-1",
                "metadata": {},
            }
            path.write_text(
                json.dumps({"version": 1, "events": [duplicate_event, duplicate_event]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "PERSISTENT_LEDGER_EVENT_INVALID"):
                PersistentLedger(path)

    def test_ledger_round_trip_is_durable_and_duplicate_post_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            ledger = PersistentLedger(path)
            account = AccountIdentity(
                loginid="VRTC12345",
                account_type="demo",
                currency="USD",
                environment="virtual",
            )
            event = LedgerEvent(
                event_id="event-1",
                intent_id="intent-1",
                account=account,
                event_type="INTENT_RESERVED",
                amount=1.0,
                currency="USD",
                occurred_at=datetime.now(timezone.utc),
                broker_transaction_id="tx-1",
                metadata={"source": "offline-test"},
            )
            self.assertTrue(ledger.post(event))
            self.assertFalse(ledger.post(event))

            restarted = PersistentLedger(path)
            events = restarted.events()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].event_id, "event-1")
            self.assertEqual(events[0].account, account)
            self.assertEqual(events[0].broker_transaction_id, "tx-1")


    def test_ledger_normalizes_identifiers_and_defensively_copies_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            ledger = PersistentLedger(path)
            account = AccountIdentity(
                loginid="VRTC12345",
                account_type="demo",
                currency="USD",
                environment="virtual",
            )
            metadata = {"source": "offline-test", "nested": {"labels": ["original"]}}
            event = LedgerEvent(
                event_id=" event-1 ",
                intent_id=" intent-1 ",
                account=account,
                event_type=" INTENT_RESERVED ",
                amount=1.0,
                currency="usd",
                occurred_at=datetime.now(timezone.utc),
                metadata=metadata,
            )

            self.assertTrue(ledger.post(event))
            metadata["nested"]["labels"].append("mutated-after-post")
            returned = ledger.events()[0]
            returned.metadata["nested"]["labels"].append("mutated-return-value")

            current = ledger.events()[0]
            self.assertEqual(current.event_id, "event-1")
            self.assertEqual(current.intent_id, "intent-1")
            self.assertEqual(current.event_type, "INTENT_RESERVED")
            self.assertEqual(current.currency, "USD")
            self.assertEqual(current.metadata["nested"]["labels"], ["original"])

            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["events"][0]["event_id"], "event-1")
            self.assertEqual(persisted["events"][0]["intent_id"], "intent-1")
            self.assertEqual(
                persisted["events"][0]["metadata"]["nested"]["labels"],
                ["original"],
            )
            duplicate = LedgerEvent(
                event_id="event-1",
                intent_id="intent-1",
                account=account,
                event_type="INTENT_RESERVED",
                amount=1.0,
                currency="USD",
                occurred_at=event.occurred_at,
                metadata={"source": "duplicate"},
            )
            self.assertFalse(ledger.post(duplicate))
            restarted = PersistentLedger(path)
            self.assertEqual(restarted.events()[0].metadata["nested"]["labels"], ["original"])

    def test_directory_fsync_failure_after_replace_poisons_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.json"
            ledger = PersistentLedger(path)
            account = AccountIdentity(
                loginid="VRTC12345",
                account_type="demo",
                currency="USD",
                environment="virtual",
            )
            event = LedgerEvent(
                event_id="event-uncertain",
                intent_id="intent-uncertain",
                account=account,
                event_type="INTENT_RESERVED",
                amount=1.0,
                currency="USD",
                occurred_at=datetime.now(timezone.utc),
                metadata={},
            )
            real_fsync = __import__("os").fsync
            calls = 0

            def fail_directory_fsync(fd):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated directory fsync failure")
                return real_fsync(fd)

            with patch("runtime.core.persistent.os.fsync", side_effect=fail_directory_fsync):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "PERSISTENT_LEDGER_DURABILITY_UNCERTAIN_STORE_POISONED",
                ):
                    ledger.post(event)

            self.assertEqual(calls, 2)
            self.assertTrue(path.exists())
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["events"][0]["event_id"], "event-uncertain")
            with self.assertRaisesRegex(RuntimeError, "PERSISTENT_LEDGER_STORE_POISONED"):
                ledger.post(event)


if __name__ == "__main__":
    unittest.main()
