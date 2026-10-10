from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.broker.executor import CapitalPlaneExecutor
from runtime.core.authority import build_intent
from runtime.core.fencing import ExecutionFence
from runtime.core.idempotency import IdempotencyStore
from runtime.core.journal import AppendOnlyJournal
from runtime.core.ledger import InMemoryLedger
from runtime.core.models import (
    AccountIdentity,
    AuthorizationContext,
    BrokerOutcome,
    BrokerResult,
    CapitalSnapshot,
    Decision,
)
from runtime.core.reconcile import Reconciler
from runtime.core.state import RuntimeStateMachine


UTC = timezone.utc


def account():
    return AccountIdentity("CRREAL", "real", "USD", "real")


def capital():
    a = account()
    return CapitalSnapshot(
        balance=200.0,
        currency="USD",
        available_balance=200.0,
        captured_at=datetime.now(UTC),
        source="test",
        account=a,
    )


def decision():
    return Decision(
        "D-EXEC",
        "S",
        "1",
        "strategy-hash",
        "R_100",
        "CALL",
        0.60,
        datetime.now(UTC),
        "market-hash",
        1.0,
        ("TEST",),
        2.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.8,
    )


def context(*, issued_at=None):
    issued = issued_at or (datetime.now(UTC) - timedelta(seconds=1))
    return AuthorizationContext(
        decision=decision(),
        account=account(),
        capital=capital(),
        config_hash="config-hash",
        authorization_id="AUTH-EXEC",
        authorization_issued_at=issued,
        authorization_expires_at=datetime.now(UTC) + timedelta(seconds=30),
        kill_switch_off=True,
        risk_approved=True,
        firewall_approved=True,
        reconciliation_healthy=True,
        final_execution_authorization=True,
    )


class FakeBroker:
    def __init__(self):
        self.calls = 0

    async def get_balance(self):
        return capital()

    async def submit_authorized_order(self, payload):
        self.calls += 1
        await asyncio.sleep(0)
        return BrokerResult(
            outcome=BrokerOutcome.ACCEPTED,
            request_id=f"REQ-{self.calls}",
            broker_transaction_id="TX-1",
            contract_id="C-1",
            raw_class="TEST_ACCEPTED",
            broker_timestamp=datetime.now(UTC),
        )


class UnknownBroker(FakeBroker):
    async def submit_authorized_order(self, payload):
        self.calls += 1
        await asyncio.sleep(0)
        return BrokerResult(
            outcome=BrokerOutcome.UNKNOWN,
            request_id=f"REQ-{self.calls}",
            raw_class="TEST_UNKNOWN",
            broker_timestamp=datetime.now(UTC),
        )


def make_executor(lock_path: Path, broker=None):
    return CapitalPlaneExecutor(
        broker or FakeBroker(),
        journal=AppendOnlyJournal(lock_path.parent / "events.ndjson"),
        ledger=InMemoryLedger(),
        idempotency=IdempotencyStore(lock_path.parent / "idempotency.json"),
        fence=ExecutionFence(),
        state=RuntimeStateMachine(),
        reconciler=Reconciler(),
        source_hash="source",
        config_hash="config-hash",
        live_lock_path=lock_path,
    )


class CapitalExecutorHardeningTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def write_live_release(path: Path):
        path.write_text(
            "live_trading_enabled: true\n"
            "FINAL_EXECUTION_AUTHORIZATION: true\n"
            "LIVE_EXECUTION: ENABLED\n"
            "capital_plane_mode: LIVE\n",
            encoding="utf-8",
        )

    async def test_kill_switch_requires_post_trigger_fresh_authorization(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)
            executor = make_executor(lock)
            executor.activate_kill_switch("TEST_TRIGGER")
            stale = context(
                issued_at=executor._kill_switch_activated_at - timedelta(seconds=1)
            )
            self.assertFalse(executor.clear_kill_switch_with_fresh_authorization(stale))

            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            fresh = context(issued_at=datetime.now(UTC) - timedelta(seconds=1))
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(fresh))
            self.assertFalse(executor.kill_switch)

    async def test_non_live_mode_cannot_reach_broker(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)
            broker = FakeBroker()
            executor = make_executor(lock, broker)
            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            auth = context()
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(auth))

            intent = build_intent(auth, proposal_id="P1", mode="SHADOW")
            token = executor.fence.acquire("test")
            outcome = await executor.execute(intent, auth, token)

            self.assertFalse(outcome.allowed)
            self.assertIn("NON_LIVE_BROKER_SUBMISSION_FORBIDDEN", outcome.reasons)
            self.assertEqual(broker.calls, 0)

    async def test_unknown_outcome_blocks_blind_retry(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)
            broker = UnknownBroker()
            executor = make_executor(lock, broker)
            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            auth = context()
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(auth))

            intent = build_intent(auth, proposal_id="P1", mode="LIVE")
            token = executor.fence.acquire("test")
            first = await executor.execute(intent, auth, token)
            second = await executor.execute(intent, auth, token)

            self.assertEqual(first.status, "RECOVERY_REQUIRED")
            self.assertIn("BROKER_OUTCOME_UNKNOWN", first.reasons)
            self.assertEqual(second.status, "RECOVERY_REQUIRED")
            self.assertIn("BROKER_OUTCOME_UNKNOWN_REQUIRES_RECONCILIATION", second.reasons)
            self.assertEqual(broker.calls, 1)


    async def test_one_percent_maximum_loss_budget_is_enforced_at_submission(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)
            from runtime.core.models import CapitalSnapshot
            small_account = AccountIdentity("CRSMALL", "real", "USD", "real")
            snapshot = CapitalSnapshot(10.0, "USD", 10.0, datetime.now(UTC), "test", small_account)

            class SmallBroker(FakeBroker):
                async def get_balance(self):
                    return snapshot

            broker = SmallBroker()
            executor = make_executor(lock, broker)
            auth = AuthorizationContext(
                decision=Decision(
                    "D-SMALL", "S", "1", "strategy-hash", "R_100", "CALL", 0.60,
                    datetime.now(UTC), "market-hash", 1.0, ("TEST",), 2.0, 1.0,
                    0.0, 0.0, 0.0, 0.8,
                ),
                account=small_account, capital=snapshot, config_hash="config-hash",
                authorization_id="AUTH-SMALL",
                authorization_issued_at=datetime.now(UTC)-timedelta(seconds=1),
                authorization_expires_at=datetime.now(UTC)+timedelta(seconds=30),
                kill_switch_off=True, risk_approved=True, firewall_approved=True,
                reconciliation_healthy=True, final_execution_authorization=True,
            )
            executor._kill_switch_activated_at = datetime.now(UTC)-timedelta(seconds=2)
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(auth))
            intent = build_intent(auth, proposal_id="P1", mode="LIVE")
            token = executor.fence.acquire("test")
            outcome = await executor.execute(intent, auth, token)
            self.assertFalse(outcome.allowed)
            self.assertIn("TRADE_RISK_BUDGET_EXCEEDED", outcome.reasons)
            self.assertEqual(broker.calls, 0)

    async def test_duplicate_concurrent_intent_has_one_broker_effect(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)
            broker = FakeBroker()
            executor = make_executor(lock, broker)
            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            auth = context()
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(auth))

            intent = build_intent(auth, proposal_id="P1", mode="LIVE")
            token = executor.fence.acquire("test")
            first, second = await asyncio.gather(
                executor.execute(intent, auth, token),
                executor.execute(intent, auth, token),
            )

            self.assertEqual(broker.calls, 1)
            self.assertEqual(
                sorted([first.status, second.status]),
                ["ACCEPTED", "ALREADY_ACCEPTED"],
            )


if __name__ == "__main__":
    unittest.main()
