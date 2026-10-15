"""Focused unit tests for AURELIA guarded execution and risk controls."""
from decimal import Decimal
import unittest

from execution.guarded_engine import (
    ExecutionHalted,
    RiskLimits,
    RiskManager,
)


class RiskManagerCircuitBreakerTests(unittest.TestCase):
    def test_daily_loss_limit_halts(self) -> None:
        risk = RiskManager(RiskLimits(
            daily_loss_fraction=Decimal("0.03"),
            consecutive_losses=3,
            max_drawdown_fraction=Decimal("0.08"),
        ))
        risk.initialize_session(Decimal("100"))
        with self.assertRaises(ExecutionHalted):
            risk.record_closed_trade(Decimal("-3.01"), Decimal("96.99"))
        self.assertTrue(risk.halted)
        self.assertEqual(risk.halt_reason, "DAILY_LOSS_LIMIT")

    def test_consecutive_loss_limit_halts(self) -> None:
        risk = RiskManager(RiskLimits(
            daily_loss_fraction=Decimal("0.20"),
            consecutive_losses=2,
            max_drawdown_fraction=Decimal("0.50"),
        ))
        risk.initialize_session(Decimal("100"))
        risk.record_closed_trade(Decimal("-1"), Decimal("99"))
        with self.assertRaises(ExecutionHalted):
            risk.record_closed_trade(Decimal("-1"), Decimal("98"))
        self.assertEqual(risk.halt_reason, "CONSECUTIVE_LOSS_LIMIT")

    def test_state_mismatch_halts_engine(self) -> None:
        # Use a minimal adapter and an explicit async trading-status callback.
        # State mismatch is tested by priming a snapshot then changing broker state.
        # The helper is intentionally not connected to Deriv and never sends orders.
        from execution.guarded_engine import AccountSnapshot, ExecutionEngine

        class FakeAdapter:
            authorized = True

            def __init__(self) -> None:
                self.balance = "100"
                self.contracts = []

            async def request(self, payload):
                if "balance" in payload:
                    return {"balance": {
                        "loginid": "TEST_ACCOUNT",
                        "currency": "USD",
                        "balance": self.balance,
                    }}
                if "portfolio" in payload:
                    return {"portfolio": {"contracts": []}}
                if "proposal_open_contract" in payload:
                    raise AssertionError("no contract-specific query expected for an empty portfolio")
                raise AssertionError("unexpected endpoint in state mismatch test")

        async def status_ok():
            return True

        import asyncio

        async def scenario():
            adapter = FakeAdapter()
            risk = RiskManager()
            engine = ExecutionEngine(
                adapter, risk, status_check=status_ok, mode="VERIFY_ONLY"
            )
            initial = await engine._broker_snapshot()
            engine.local_snapshot = initial
            adapter.balance = "99.99"
            with self.assertRaises(ExecutionHalted) as caught:
                await engine.verify_only()
            self.assertEqual(str(caught.exception), "STATE_MISMATCH")
            self.assertTrue(engine.halted)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
