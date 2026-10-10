from __future__ import annotations

import unittest

from runtime.ops.readiness_orchestrator import (
    _minimum_capital_gate,
    _minimum_available_capital_gate,
    _minimum_stake_risk_gate,
)


class ReadinessMinimumCapitalTests(unittest.TestCase):
    def test_balance_at_or_below_150_fails(self):
        for balance in (0.0, 1.49, 1.50):
            with self.subTest(balance=balance):
                self.assertEqual(_minimum_capital_gate(balance).status, "FAIL")

    def test_balance_above_150_passes_capital_floor(self):
        self.assertEqual(_minimum_capital_gate(1.51).status, "PASS")

    def test_unknown_or_nonfinite_balance_does_not_pass(self):
        for balance in (None, float("nan"), float("inf"), True):
            with self.subTest(balance=balance):
                self.assertNotEqual(_minimum_capital_gate(balance).status, "PASS")

    def test_spendable_balance_must_be_above_floor(self):
        self.assertEqual(_minimum_available_capital_gate(1.50).status, "FAIL")
        self.assertEqual(_minimum_available_capital_gate(1.51).status, "PASS")
        self.assertEqual(_minimum_available_capital_gate(None).status, "UNKNOWN")

    def test_minimum_stake_must_fit_inside_one_percent_of_available_balance(self):
        self.assertEqual(_minimum_stake_risk_gate(100.0, 1.0).status, "PASS")
        self.assertEqual(_minimum_stake_risk_gate(99.99, 1.0).status, "FAIL")
        self.assertEqual(_minimum_stake_risk_gate(None, 1.0).status, "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
