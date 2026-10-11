import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from runtime.autonomous_loop import (
    _extract_net_delta,
    AutonomousExecutionLoop,
    validate_incoming_tick,
    _decision_symbol_error,
)
from runtime.broker.executor import CapitalPlaneExecutor
from runtime.core.fencing import ExecutionFence
from runtime.core.idempotency import IdempotencyStore
from runtime.core.journal import AppendOnlyJournal
from runtime.core.ledger import InMemoryLedger
from runtime.core.models import (
    AccountIdentity,
    BrokerOutcome,
    BrokerResult,
    CapitalSnapshot,
    Decision,
    MarketTick,
)
from runtime.core.reconcile import Reconciler
from runtime.core.state import RuntimeStateMachine




class _FakeProvider:
    def __init__(self):
        self.proposal_calls = 0

    async def next_decision(self, *, tick, capital, account):
        return None

    def proposal_parameters(self, *, decision, capital, account):
        self.proposal_calls += 1
        return {
            "contract_type": "CALL",
            "currency": account.currency,
            "underlying_symbol": decision.symbol,
            "duration": 1,
            "duration_unit": "s",
        }

    def control_snapshot(self, *, decision, tick, capital):
        return {}


class _FakeAdapter:
    def __init__(self):
        self.submitted = 0
        self.proposals = 0
        self.transport = object()

    async def request_proposal(self, parameters):
        self.proposals += 1
        return "PROP-1"

    async def submit_authorized_order(self, payload):
        self.submitted += 1
        return BrokerResult(BrokerOutcome.ACCEPTED, "REQ-1", "TX-1", "C-1")

    async def get_balance(self):
        account = AccountIdentity("CRTEST", "real", "USD", "real")
        return CapitalSnapshot(10.0, "USD", 10.0, datetime.now(timezone.utc), "test", account)

    async def portfolio(self):
        return []


async def _async_blocked_loop_test():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        lock = root / "LIVE_LOCK.yaml"
        lock.write_text(
            "live_trading_enabled: false\n"
            "FINAL_EXECUTION_AUTHORIZATION: false\n"
            "LIVE_EXECUTION: BLOCKED\n"
            "capital_plane_mode: VERIFY_ONLY\n",
            encoding="utf-8",
        )
        adapter = _FakeAdapter()
        executor = CapitalPlaneExecutor(
            adapter,
            journal=AppendOnlyJournal(root / "events.ndjson"),
            ledger=InMemoryLedger(),
            idempotency=IdempotencyStore(root / "idempotency.json"),
            fence=ExecutionFence(),
            state=RuntimeStateMachine(),
            reconciler=Reconciler(),
            source_hash="test",
            config_hash="cfg",
            live_lock_path=lock,
        )
        provider = _FakeProvider()
        loop = AutonomousExecutionLoop(
            adapter=adapter,
            executor=executor,
            decision_provider=provider,
            runtime_config_hash="cfg",
            symbols=("R_100",),
        )
        account = AccountIdentity("CRTEST", "real", "USD", "real")
        capital = CapitalSnapshot(10.0, "USD", 10.0, datetime.now(timezone.utc), "test", account)
        decision = Decision(
            "D-BLOCKED", "S", "1", "strategy-hash", "R_100", "CALL", 0.60,
            datetime.now(timezone.utc), "market-hash", 1.0, ("TEST",),
            2.0, 1.0, 0.0, 0.0, 0.0, 0.8,
        )
        result = await loop.execute_decision(
            decision=decision,
            capital=capital,
            account=account,
            controls={
                "risk_approved": True,
                "firewall_approved": True,
                "reconciliation_healthy": True,
                "final_execution_authorization": True,
                "live_trading_enabled": True,
                "probability_calibrated": True,
                "probability_fresh": True,
                "probability_drift_ok": True,
                "market_data_validated": True,
                "exposure_approved": True,
            },
        )
        assert result.status == "BLOCKED"
        # $10 available balance cannot fund a $1 minimum stake inside a 1%
        # maximum-loss budget. The capital plane must block before even
        # requesting a proposal, not only before buy submission.
        assert provider.proposal_calls == 0
        assert adapter.proposals == 0
        assert adapter.submitted == 0
        assert executor.kill_switch is True

class AutonomousLoopTests(unittest.TestCase):
    def test_live_lock_blocks_autonomous_capital_submission(self):
        asyncio.run(_async_blocked_loop_test())

    def test_open_portfolio_blocks_before_proposal_request(self):
        async def scenario():
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                lock = root / "LIVE_LOCK.yaml"
                lock.write_text(
                    "schema: aurelia.live_lock.v1\n"
                    "live_trading_enabled: true\n"
                    "FINAL_EXECUTION_AUTHORIZATION: true\n"
                    "LIVE_EXECUTION: ENABLED\n"
                    "capital_plane_mode: LIVE\n"
                    "research_capital_authority: false\n"
                    "external_repositories_capital_forbidden: true\n"
                    "blind_resubmission: false\n"
                    "kill_switch_independent: true\n",
                    encoding="utf-8",
                )

                class _OpenPositionAdapter(_FakeAdapter):
                    async def portfolio(self):
                        return [{"contract_id": "C-EXTERNAL", "buy_price": "1.00"}]

                adapter = _OpenPositionAdapter()
                executor = CapitalPlaneExecutor(
                    adapter,
                    journal=AppendOnlyJournal(root / "events.ndjson"),
                    ledger=InMemoryLedger(),
                    idempotency=IdempotencyStore(root / "idempotency.json"),
                    fence=ExecutionFence(),
                    state=RuntimeStateMachine(),
                    reconciler=Reconciler(),
                    source_hash="test",
                    config_hash="cfg",
                    live_lock_path=lock,
                )
                provider = _FakeProvider()
                loop = AutonomousExecutionLoop(
                    adapter=adapter, executor=executor, decision_provider=provider,
                    runtime_config_hash="cfg", symbols=("R_100",),
                )
                account = AccountIdentity("CRTEST", "real", "USD", "real")
                capital = CapitalSnapshot(200.0, "USD", 200.0, datetime.now(timezone.utc), "test", account)
                decision = Decision(
                    "D-OPEN-POSITION", "S", "1", "strategy-hash", "R_100", "CALL", 0.60,
                    datetime.now(timezone.utc), "market-hash", 2.0, ("TEST",),
                    2.0, 1.0, 0.0, 0.0, 0.0, 0.8,
                )
                result = await loop.execute_decision(
                    decision=decision, capital=capital, account=account,
                    controls={
                        "risk_approved": True, "firewall_approved": True,
                        "reconciliation_healthy": True, "final_execution_authorization": True,
                        "live_trading_enabled": True, "probability_calibrated": True,
                        "probability_fresh": True, "probability_drift_ok": True,
                        "market_data_validated": True, "exposure_approved": True,
                    },
                )
                assert result.status == "BLOCKED"
                assert "OPEN_POSITIONS_PRESENT" in result.reasons
                assert provider.proposal_calls == 0
                assert adapter.proposals == 0
                assert adapter.submitted == 0

        asyncio.run(scenario())

    def test_release_lock_blocks_affordable_stake_before_proposal(self):
        async def scenario():
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                lock = root / "LIVE_LOCK.yaml"
                lock.write_text(
                    "live_trading_enabled: true\n"
                    "FINAL_EXECUTION_AUTHORIZATION: true\n"
                    "LIVE_EXECUTION: BLOCKED\n"
                    "capital_plane_mode: LIVE\n",
                    encoding="utf-8",
                )
                adapter = _FakeAdapter()
                executor = CapitalPlaneExecutor(
                    adapter,
                    journal=AppendOnlyJournal(root / "events.ndjson"),
                    ledger=InMemoryLedger(),
                    idempotency=IdempotencyStore(root / "idempotency.json"),
                    fence=ExecutionFence(),
                    state=RuntimeStateMachine(),
                    reconciler=Reconciler(),
                    source_hash="test",
                    config_hash="cfg",
                    live_lock_path=lock,
                )
                provider = _FakeProvider()
                loop = AutonomousExecutionLoop(
                    adapter=adapter,
                    executor=executor,
                    decision_provider=provider,
                    runtime_config_hash="cfg",
                    symbols=("R_100",),
                )
                account = AccountIdentity("CRTEST", "real", "USD", "real")
                capital = CapitalSnapshot(200.0, "USD", 200.0, datetime.now(timezone.utc), "test", account)
                decision = Decision(
                    "D-LOCKED", "S", "1", "strategy-hash", "R_100", "CALL", 0.60,
                    datetime.now(timezone.utc), "market-hash", 2.0, ("TEST",),
                    2.0, 1.0, 0.0, 0.0, 0.0, 0.8,
                )
                result = await loop.execute_decision(
                    decision=decision,
                    capital=capital,
                    account=account,
                    controls={
                        "risk_approved": True, "firewall_approved": True,
                        "reconciliation_healthy": True, "final_execution_authorization": True,
                        "live_trading_enabled": True, "probability_calibrated": True,
                        "probability_fresh": True, "probability_drift_ok": True,
                        "market_data_validated": True, "exposure_approved": True,
                    },
                )
                assert result.status == "BLOCKED"
                assert provider.proposal_calls == 0
                assert adapter.proposals == 0
                assert adapter.submitted == 0
                assert executor.kill_switch is True

        asyncio.run(scenario())

    def test_fault_latched_switch_blocks_before_proposal_request(self):
        async def scenario():
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                lock = root / "LIVE_LOCK.yaml"
                lock.write_text(
                    "schema: aurelia.live_lock.v1\n"
                    "live_trading_enabled: true\n"
                    "FINAL_EXECUTION_AUTHORIZATION: true\n"
                    "LIVE_EXECUTION: ENABLED\n"
                    "capital_plane_mode: LIVE\n"
                    "research_capital_authority: false\n"
                    "external_repositories_capital_forbidden: true\n"
                    "blind_resubmission: false\n"
                    "kill_switch_independent: true\n",
                    encoding="utf-8",
                )
                adapter = _FakeAdapter()
                executor = CapitalPlaneExecutor(
                    adapter,
                    journal=AppendOnlyJournal(root / "events.ndjson"),
                    ledger=InMemoryLedger(),
                    idempotency=IdempotencyStore(root / "idempotency.json"),
                    fence=ExecutionFence(),
                    state=RuntimeStateMachine(),
                    reconciler=Reconciler(),
                    source_hash="source",
                    config_hash="cfg",
                    live_lock_path=lock,
                )
                executor._fault_latched = True
                executor._kill_switch_reason = "STATE_MISMATCH"
                provider = _FakeProvider()
                loop = AutonomousExecutionLoop(
                    adapter=adapter, executor=executor, decision_provider=provider,
                    runtime_config_hash="cfg", symbols=("R_100",),
                )
                identity = AccountIdentity("CRTEST", "real", "USD", "real")
                capital = CapitalSnapshot(200.0, "USD", 200.0, datetime.now(timezone.utc), "test", identity)
                decision = Decision(
                    "D-FAULT-LATCHED", "S", "1", "strategy-hash", "R_100", "CALL", 0.60,
                    datetime.now(timezone.utc), "market-hash", 2.0, ("TEST",),
                    2.0, 1.0, 0.0, 0.0, 0.0, 0.8,
                )
                result = await loop.execute_decision(
                    decision=decision, capital=capital, account=identity,
                    controls={
                        "risk_approved": True, "firewall_approved": True,
                        "reconciliation_healthy": True, "final_execution_authorization": True,
                        "live_trading_enabled": True, "probability_calibrated": True,
                        "probability_fresh": True, "probability_drift_ok": True,
                        "market_data_validated": True, "exposure_approved": True,
                    },
                )
                assert result.status == "RECOVERY_REQUIRED"
                assert "KILL_SWITCH_FAULT_LATCHED" in result.reasons
                assert provider.proposal_calls == 0
                assert adapter.proposals == 0
                assert adapter.submitted == 0

        asyncio.run(scenario())

    def test_proposal_id_is_bound_into_final_authorized_intent(self):
        from types import SimpleNamespace

        async def scenario():
            loop = object.__new__(AutonomousExecutionLoop)
            captured = {}

            class _AuthorizationExecutor:
                async def preflight_authorization(self, **kwargs):
                    return SimpleNamespace(allowed=True), object()

                def clear_kill_switch_with_fresh_authorization(self, authorization):
                    return True

            loop.executor = _AuthorizationExecutor()
            loop.executor.kill_switch = True
            loop.runtime_config_hash = "cfg"

            async def fake_fresh_authorization(**kwargs):
                captured.update(kwargs)
                return object(), object()

            loop._fresh_authorization = fake_fresh_authorization
            result = await loop._prepare_live_intent(
                decision=object(),
                capital=object(),
                account=object(),
                controls={},
                proposal_id="DERIV-PROPOSAL-123",
            )
            assert result[0] is not None and result[1] is not None
            assert captured["proposal_id"] == "DERIV-PROPOSAL-123"

        asyncio.run(scenario())

    def test_multi_symbol_tick_readers_are_not_cancelled_by_faster_stream(self):
        async def scenario():
            seen = []
            identity = AccountIdentity("CRTEST", "real", "USD", "real")

            class _FanInAdapter:
                async def get_balance(self):
                    return CapitalSnapshot(
                        200.0, "USD", 200.0, datetime.now(timezone.utc), "test", identity
                    )

                def subscribe_ticks(self, symbol):
                    async def stream():
                        if symbol == "R_75":
                            await asyncio.sleep(0.05)
                        while True:
                            now = datetime.now(timezone.utc)
                            yield MarketTick(
                                symbol=symbol,
                                quote=100.0,
                                epoch=int(now.timestamp()),
                                received_at=now,
                            )
                            await asyncio.sleep(0.01)
                    return stream()

            class _Provider:
                loop = None

                async def next_decision(self, *, tick, capital, account):
                    seen.append(tick.symbol)
                    if {"R_100", "R_75"}.issubset(set(seen)):
                        self.loop.stop()
                    return None

                def proposal_parameters(self, **kwargs):
                    return {}

                def control_snapshot(self, **kwargs):
                    return {}

            class _Executor:
                daily_risk_guard = None

                def activate_kill_switch(self, reason):
                    return None

                def _log(self, event, payload):
                    return None

            provider = _Provider()
            loop = AutonomousExecutionLoop(
                adapter=_FanInAdapter(),
                executor=_Executor(),
                decision_provider=provider,
                runtime_config_hash="cfg",
                symbols=("R_100", "R_75"),
            )
            provider.loop = loop
            await asyncio.wait_for(loop.run(), timeout=1.0)
            assert "R_100" in seen and "R_75" in seen

        asyncio.run(scenario())

    def test_decision_must_match_exact_tick_and_allowlisted_symbol(self):
        now = datetime.now(timezone.utc)
        tick = MarketTick("R_100", 100.0, int(now.timestamp()), now)
        decision = Decision(
            "D-SYMBOL", "S", "1", "strategy-hash", "R_100", "CALL", 0.60,
            now, "market-hash", 1.0, ("TEST",), 2.0, 1.0, 0.0, 0.0, 0.0, 0.8,
        )
        self.assertIsNone(_decision_symbol_error(decision, tick, ("R_100", "R_75")))
        wrong_tick = MarketTick("R_75", 100.0, int(now.timestamp()), now)
        self.assertEqual(
            _decision_symbol_error(decision, wrong_tick, ("R_100", "R_75")),
            "DECISION_TICK_SYMBOL_MISMATCH",
        )
        self.assertEqual(
            _decision_symbol_error(decision, tick, ("R_75",)),
            "DECISION_SYMBOL_NOT_ALLOWLISTED",
        )

    def test_incoming_tick_validation_fails_closed(self):
        now = datetime.now(timezone.utc)
        current = MarketTick(
            symbol="R_100",
            quote=100.0,
            epoch=int(now.timestamp()),
            received_at=now,
        )
        self.assertIsNone(
            validate_incoming_tick(current, expected_symbol="R_100", now=now)
        )
        self.assertEqual(
            validate_incoming_tick(current, expected_symbol="R_75", now=now),
            "MARKET_DATA_SYMBOL_MISMATCH",
        )
        self.assertEqual(
            validate_incoming_tick(
                current, expected_symbol="R_100", now=now,
                previous_epoch=current.epoch + 1,
            ),
            "MARKET_DATA_OUT_OF_ORDER",
        )
        stale = MarketTick(
            symbol="R_100",
            quote=100.0,
            epoch=int((now - __import__("datetime").timedelta(seconds=20)).timestamp()),
            received_at=now,
        )
        self.assertEqual(
            validate_incoming_tick(stale, expected_symbol="R_100", now=now),
            "MARKET_DATA_SOURCE_AGE_INVALID",
        )
        future = MarketTick(
            symbol="R_100",
            quote=100.0,
            epoch=int((now + __import__("datetime").timedelta(seconds=10)).timestamp()),
            received_at=now,
        )
        self.assertEqual(
            validate_incoming_tick(future, expected_symbol="R_100", now=now),
            "MARKET_DATA_SOURCE_AGE_INVALID",
        )

    def test_extract_profit(self):
        self.assertEqual(_extract_net_delta({"profit": "2.5"}, 1.0), 2.5)

    def test_extract_payout_minus_buy(self):
        self.assertEqual(_extract_net_delta({"payout": "4.0", "buy_price": "1.5"}, 1.0), 2.5)

    def test_unresolved_settlement_is_none(self):
        self.assertIsNone(_extract_net_delta({"contract_id": "1"}, 1.0))


if __name__ == "__main__":
    unittest.main()
