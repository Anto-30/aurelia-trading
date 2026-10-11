from __future__ import annotations

import unittest
from datetime import datetime, timezone

from runtime.core.models import AccountIdentity, CapitalSnapshot, MarketTick, utc_now
from runtime.ops.readiness_orchestrator import (
    _minimum_available_capital_gate,
    _minimum_capital_gate,
    _minimum_stake_risk_gate,
)


class FailClosedNumericInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.account = AccountIdentity("CRTEST", "real", "USD", "real")

    def test_capital_snapshot_rejects_malformed_and_overflowing_amounts(self) -> None:
        for bad in (True, "100", float("nan"), float("inf"), 10**10000):
            with self.subTest(value_type=type(bad).__name__):
                snapshot = CapitalSnapshot(
                    balance=bad,
                    currency="USD",
                    available_balance=bad,
                    captured_at=utc_now(),
                    source="unit-test",
                    account=self.account,
                )
                self.assertFalse(snapshot.is_valid())

    def test_capital_snapshot_requires_timezone_aware_freshness(self) -> None:
        snapshot = CapitalSnapshot(
            balance=100.0,
            currency="USD",
            available_balance=100.0,
            captured_at=datetime.now(),
            source="unit-test",
            account=self.account,
        )
        self.assertFalse(snapshot.is_valid())

    def test_market_tick_rejects_malformed_and_overflowing_quotes(self) -> None:
        for quote in (True, "1.2", float("nan"), float("inf"), 10**10000):
            with self.subTest(value_type=type(quote).__name__):
                tick = MarketTick("R_100", quote, 1, utc_now())
                self.assertFalse(tick.valid())

    def test_readiness_numeric_gates_return_unknown_for_overflowing_inputs(self) -> None:
        too_large = 10**10000
        self.assertEqual(_minimum_capital_gate(too_large).status, "UNKNOWN")
        self.assertEqual(_minimum_available_capital_gate(too_large).status, "UNKNOWN")
        self.assertEqual(_minimum_stake_risk_gate(too_large, 1.0).status, "UNKNOWN")
        self.assertEqual(_minimum_stake_risk_gate(100.0, too_large).status, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
