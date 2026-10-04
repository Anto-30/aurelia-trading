import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from runtime.autonomous_loop import _extract_net_delta, AutonomousExecutionLoop
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


async def _async_blocked_loop_test():
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        lock = root / "LIVE_LOCK.yaml"
        lock.write_text(
            "live_trading_enabled: false\\n"
            "FINAL_EXECUTION_AUTHORIZATION: false\\n"
            "LIVE_EXECUTION: BLOCKED\\n"
            "capital_plane_mode: VERIFY_ONLY\\n",
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
        assert adapter.proposals == 1
        assert adapter.submitted == 0
        assert executor.kill_switch is True

class AutonomousLoopTests(unittest.TestCase):
    def test_live_lock_blocks_autonomous_capital_submission(self):
        asyncio.run(_async_blocked_loop_test())

    def test_extract_profit(self):
        self.assertEqual(_extract_net_delta({"profit": "2.5"}, 1.0), 2.5)

    def test_extract_payout_minus_buy(self):
        self.assertEqual(_extract_net_delta({"payout": "4.0", "buy_price": "1.5"}, 1.0), 2.5)

    def test_unresolved_settlement_is_none(self):
        self.assertIsNone(_extract_net_delta({"contract_id": "1"}, 1.0))


if __name__ == "__main__":
    unittest.main()
