from __future__ import annotations

import asyncio
import json
from dataclasses import replace
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
from runtime.core.operator_reset import create_operator_reset_record
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
        self.proposal_calls = 0

    async def request_proposal(self, parameters):
        self.proposal_calls += 1
        return f"QUOTE-{self.proposal_calls}"

    async def get_balance(self):
        return capital()

    async def portfolio(self):
        return []

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


class BalanceMismatchBroker(FakeBroker):
    async def get_balance(self):
        snapshot = capital()
        return CapitalSnapshot(
            balance=snapshot.balance - 0.25,
            currency=snapshot.currency,
            available_balance=snapshot.available_balance - 0.25,
            captured_at=datetime.now(UTC),
            source="test:mismatched-broker",
            account=snapshot.account,
        )


TEST_OPERATOR_RESET_KEY = "unit-test-operator-reset-key-at-least-32-characters"


def make_executor(lock_path: Path, broker=None, *, kill_switch_state_path=None, source_hash="source"):
    return CapitalPlaneExecutor(
        broker or FakeBroker(),
        journal=AppendOnlyJournal(lock_path.parent / "events.ndjson"),
        ledger=InMemoryLedger(),
        idempotency=IdempotencyStore(lock_path.parent / "idempotency.json"),
        fence=ExecutionFence(),
        state=RuntimeStateMachine(),
        reconciler=Reconciler(),
        source_hash=source_hash,
        config_hash="config-hash",
        live_lock_path=lock_path,
        kill_switch_state_path=kill_switch_state_path,
        operator_reset_path=lock_path.parent / "operator-reset.json",
        operator_reset_signing_key=TEST_OPERATOR_RESET_KEY,
    )


def write_operator_reset(executor, authorization):
    path = executor._operator_reset_path
    path.parent.mkdir(parents=True, exist_ok=True)
    record = create_operator_reset_record(
        signing_key=executor._operator_reset_signing_key,
        operator_id="unit-test-operator",
        reason=executor._kill_switch_reason,
        source_sha=executor.source_hash,
        fault_source_sha=executor._fault_source_sha or executor.source_hash,
        account_loginid=authorization.account.loginid,
        kill_switch_generation=executor._kill_switch_generation,
    )
    path.write_text(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return path


async def bound_intent(executor, authorization, *, mode="LIVE"):
    if mode != "LIVE":
        return build_intent(authorization, proposal_id="NONLIVE-TEST", mode=mode)
    decision = authorization.decision
    direction = str(decision.direction).strip().upper()
    contract_type = (
        "CALL" if direction in {"CALL", "UP", "RISE", "BUY", "LONG"}
        else "PUT" if direction in {"PUT", "DOWN", "FALL", "SELL", "SHORT"}
        else ""
    )
    parameters = {
        "contract_type": contract_type,
        "currency": authorization.account.currency,
        "underlying_symbol": decision.symbol,
        "basis": "stake",
        "amount": float(decision.risk_requested_stake),
    }
    proposal_id = await executor.prepare_proposal(parameters)
    parameter_hash = executor.proposal_binding_hash(proposal_id)
    if parameter_hash is None:
        raise AssertionError("test proposal binding was not registered")
    return build_intent(
        authorization,
        proposal_id=proposal_id,
        mode=mode,
        proposal_parameters_hash=parameter_hash,
    )


class CapitalExecutorHardeningTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def write_live_release(path: Path):
        path.write_text(
            "live_trading_enabled: true\n"
            "FINAL_EXECUTION_AUTHORIZATION: true\n"
            "LIVE_EXECUTION: ENABLED\n"
            "capital_plane_mode: LIVE\n"
            "research_capital_authority: false\n"
            "external_repositories_capital_forbidden: true\n"
            "blind_resubmission: false\n"
            "kill_switch_independent: true\n"
            "schema: aurelia.live_lock.v1\n",
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
            self.assertFalse(executor.clear_kill_switch_with_fresh_authorization(fresh))
            write_operator_reset(executor, fresh)
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(fresh))
            self.assertFalse(executor.kill_switch)

    async def test_persisted_fault_latch_survives_restart_and_requires_signed_reset(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lock = root / "LIVE_LOCK.yaml"
            state_path = root / "kill-switch-state.json"
            self.write_live_release(lock)

            first = make_executor(lock, kill_switch_state_path=state_path)
            first._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            startup_auth = context(issued_at=datetime.now(UTC) - timedelta(milliseconds=100))
            self.assertTrue(first.clear_kill_switch_with_fresh_authorization(startup_auth))

            first.activate_kill_switch("PERSISTED_TEST_FAULT")
            restarted = make_executor(
                lock, kill_switch_state_path=state_path, source_hash="source-after-upgrade"
            )
            self.assertTrue(restarted.kill_switch)
            self.assertTrue(restarted._fault_latched)
            fresh = context(issued_at=datetime.now(UTC))
            self.assertFalse(restarted.clear_kill_switch_with_fresh_authorization(fresh))

            write_operator_reset(restarted, fresh)
            reset_record = json.loads(restarted._operator_reset_path.read_text(encoding="utf-8"))
            self.assertEqual(reset_record["source_sha"], "source-after-upgrade")
            self.assertEqual(reset_record["fault_source_sha"], "source")
            self.assertTrue(restarted.clear_kill_switch_with_fresh_authorization(fresh))
            self.assertFalse(restarted.kill_switch)
            self.assertEqual(json.loads(state_path.read_text())["state"], "CLEARED")

            # A clean process restart relocks for fresh startup authorization,
            # but does not relatch the already-reset historical fault.
            next_process = make_executor(
                lock, kill_switch_state_path=state_path, source_hash="source-after-upgrade"
            )
            self.assertTrue(next_process.kill_switch)
            self.assertFalse(next_process._fault_latched)
            next_auth = context(issued_at=datetime.now(UTC))
            self.assertTrue(next_process.clear_kill_switch_with_fresh_authorization(next_auth))

    async def test_kill_switch_cannot_clear_with_mismatched_capital_account_binding(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)
            executor = make_executor(lock)
            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            valid = context()
            demo_binding = AccountIdentity(
                loginid=valid.account.loginid,
                account_type="real",
                currency=valid.account.currency,
                environment="demo",
            )
            invalid = replace(valid, capital=replace(valid.capital, account=demo_binding))
            self.assertTrue(invalid.capital.is_valid())
            self.assertFalse(executor.clear_kill_switch_with_fresh_authorization(invalid))
            self.assertTrue(executor.kill_switch)

    async def test_kill_switch_cannot_clear_with_non_real_account_environment(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)
            executor = make_executor(lock)
            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            valid = context()
            non_real = replace(valid, account=replace(valid.account, environment="demo"))
            self.assertFalse(executor.clear_kill_switch_with_fresh_authorization(non_real))
            self.assertTrue(executor.kill_switch)

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

    async def test_pre_submission_state_mismatch_trips_kill_and_halts(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)
            broker = BalanceMismatchBroker()
            executor = make_executor(lock, broker)
            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            auth = context()
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(auth))

            intent = await bound_intent(executor, auth)
            token = executor.fence.acquire("test")
            outcome = await executor.execute(intent, auth, token)

            self.assertFalse(outcome.allowed)
            self.assertEqual(outcome.status, "RECOVERY_REQUIRED")
            self.assertIn("STATE_MISMATCH", outcome.reasons)
            self.assertTrue(executor.kill_switch)
            self.assertEqual(broker.calls, 0)
            self.assertIn("STATE_MISMATCH", (Path(td) / "events.ndjson").read_text())

    async def test_unknown_outcome_blocks_blind_retry(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)
            broker = UnknownBroker()
            executor = make_executor(lock, broker)
            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            auth = context()
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(auth))

            intent = await bound_intent(executor, auth)
            token = executor.fence.acquire("test")
            first = await executor.execute(intent, auth, token)
            second = await executor.execute(intent, auth, token)

            self.assertEqual(first.status, "RECOVERY_REQUIRED")
            self.assertIn("BROKER_OUTCOME_UNKNOWN", first.reasons)
            self.assertEqual(second.status, "RECOVERY_REQUIRED")
            self.assertIn("BROKER_OUTCOME_UNKNOWN_REQUIRES_RECONCILIATION", second.reasons)
            self.assertEqual(broker.calls, 1)


    async def test_unresolved_unknown_blocks_other_intents_and_kill_switch_clear(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)
            broker = UnknownBroker()
            executor = make_executor(lock, broker)
            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            auth = context()
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(auth))

            first_intent = await bound_intent(executor, auth)
            first = await executor.execute(
                first_intent, auth, executor.fence.acquire("first-unknown")
            )
            self.assertEqual(first.status, "RECOVERY_REQUIRED")
            self.assertTrue(executor.kill_switch)
            self.assertEqual(
                executor.idempotency.unresolved_unknown_intents(),
                (first_intent.intent_id,),
            )

            second_decision = replace(decision(), decision_id="D-SECOND-INTENT")
            second_auth = replace(
                context(),
                decision=second_decision,
                authorization_id="AUTH-SECOND-INTENT",
            )
            second_intent = await bound_intent(executor, second_auth)
            before_calls = broker.calls
            second = await executor.execute(
                second_intent, second_auth, executor.fence.acquire("second-intent")
            )
            self.assertEqual(second.status, "RECOVERY_REQUIRED")
            self.assertIn("UNRESOLVED_BROKER_OUTCOME", second.reasons)
            self.assertEqual(broker.calls, before_calls)
            self.assertFalse(
                executor.clear_kill_switch_with_fresh_authorization(
                    replace(
                        context(),
                        authorization_issued_at=datetime.now(UTC),
                        authorization_id="AUTH-MUST-NOT-CLEAR",
                    )
                )
            )

            # The test broker's deterministic state is known to contain no
            # economic effect for UNKNOWN responses. Resolution remains an
            # explicit evidence-bound operation, never an automatic retry.
            executor.idempotency.resolve_unknown_outcome(
                first_intent.intent_id,
                broker_state_known=True,
                reconciliation_healthy=True,
                economic_effect_confirmed=False,
                broker_transaction_id=None,
                resolution_evidence_id="TEST-RECOVERY-EVIDENCE-001",
            )
            self.assertEqual(executor.idempotency.unresolved_unknown_intents(), ())
            fresh = replace(
                context(),
                authorization_issued_at=datetime.now(UTC),
                authorization_id="AUTH-AFTER-RECOVERY",
            )
            write_operator_reset(executor, fresh)
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(fresh))

    async def test_open_portfolio_blocks_new_authorized_order(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)

            class OpenPositionBroker(FakeBroker):
                async def portfolio(self):
                    return [{"contract_id": "C-EXTERNAL", "buy_price": "1.00"}]

            broker = OpenPositionBroker()
            executor = make_executor(lock, broker)
            auth = context()
            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(auth))
            intent = await bound_intent(executor, auth)
            result = await executor.execute(intent, auth, executor.fence.acquire("open-position-test"))
            self.assertFalse(result.allowed)
            self.assertIn("OPEN_POSITIONS_PRESENT", result.reasons)
            self.assertEqual(broker.calls, 0)

    async def test_unavailable_portfolio_state_trips_kill_switch(self):
        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)

            class UnavailablePortfolioBroker(FakeBroker):
                async def portfolio(self):
                    raise RuntimeError("portfolio unavailable")

            broker = UnavailablePortfolioBroker()
            executor = make_executor(lock, broker)
            auth = context()
            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(auth))
            intent = await bound_intent(executor, auth)
            result = await executor.execute(intent, auth, executor.fence.acquire("portfolio-unavailable-test"))
            self.assertFalse(result.allowed)
            self.assertEqual(result.status, "RECOVERY_REQUIRED")
            self.assertIn("PORTFOLIO_STATE_UNAVAILABLE", result.reasons)
            self.assertTrue(executor.kill_switch)
            self.assertEqual(broker.calls, 0)

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
            intent = await bound_intent(executor, auth)
            token = executor.fence.acquire("test")
            outcome = await executor.execute(intent, auth, token)
            self.assertFalse(outcome.allowed)
            self.assertIn("TRADE_RISK_BUDGET_EXCEEDED", outcome.reasons)
            self.assertEqual(broker.calls, 0)

    async def test_balance_at_or_below_1_50_kills_and_never_submits(self):
        class LowBalanceBroker(FakeBroker):
            def __init__(self, balance_value, available_value):
                super().__init__()
                self.balance_value = balance_value
                self.available_value = available_value

            async def get_balance(self):
                return CapitalSnapshot(
                    balance=self.balance_value,
                    currency="USD",
                    available_balance=self.available_value,
                    captured_at=datetime.now(UTC),
                    source="test:low-balance",
                    account=account(),
                )

        for balance_value, available_value in ((1.50, 1.50), (2.00, 1.50), (1.50, 1.40)):
            with self.subTest(balance=balance_value, available=available_value):
                with tempfile.TemporaryDirectory() as td:
                    lock = Path(td) / "LIVE_LOCK.yaml"
                    self.write_live_release(lock)
                    broker = LowBalanceBroker(balance_value, available_value)
                    executor = make_executor(lock, broker)
                    executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
                    auth = context()  # Stale/higher authorization must not override broker truth.
                    self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(auth))

                    intent = await bound_intent(executor, auth)
                    token = executor.fence.acquire("test")
                    outcome = await executor.execute(intent, auth, token)

                    self.assertFalse(outcome.allowed)
                    self.assertEqual(outcome.status, "BLOCKED")
                    self.assertIn("BALANCE_AT_OR_BELOW_MINIMUM_CAPITAL", outcome.reasons)
                    self.assertTrue(executor.kill_switch)
                    self.assertEqual(broker.calls, 0)
                    self.assertIn("BALANCE_AT_OR_BELOW_MINIMUM_CAPITAL",
                                  (Path(td) / "events.ndjson").read_text())

    async def test_duplicate_concurrent_intent_has_one_broker_effect(self):

        with tempfile.TemporaryDirectory() as td:
            lock = Path(td) / "LIVE_LOCK.yaml"
            self.write_live_release(lock)
            broker = FakeBroker()
            executor = make_executor(lock, broker)
            executor._kill_switch_activated_at = datetime.now(UTC) - timedelta(seconds=2)
            auth = context()
            self.assertTrue(executor.clear_kill_switch_with_fresh_authorization(auth))

            intent = await bound_intent(executor, auth)
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
