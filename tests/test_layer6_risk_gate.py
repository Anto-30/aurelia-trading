from __future__ import annotations

import math
import time
import unittest

from runtime.core.layer6_risk_gate import Layer6RiskGate, RiskPolicy, RiskRequest


def policy(**overrides):
    values = {
        "max_daily_loss": 5.0,
        "max_position_size": 2.0,
        "max_total_exposure": 5.0,
        "timeout_ms": 50,
    }
    values.update(overrides)
    return RiskPolicy(**values)


def request(**overrides):
    values = {
        "symbol": "R_100",
        "direction": "CALL",
        "stake": 1.0,
        "available_balance": 100.0,
        "daily_pnl": 0.0,
        "existing_exposure": 0.0,
        "pending_exposure": 0.0,
        "concurrent_exposure": 0.0,
        "correlated_exposure": 0.0,
        "account_verified": True,
        "state_verified": True,
        "kill_switch_active": False,
    }
    values.update(overrides)
    return RiskRequest(**values)


class Layer6RiskGateTests(unittest.TestCase):
    def test_happy_path_passes_risk_gate_but_does_not_grant_capital_authority(self):
        result = Layer6RiskGate(policy(), enabled=True).evaluate(request())
        self.assertTrue(result.risk_approved)
        self.assertEqual(result.reason, "RISK_CHECKS_PASSED")
        self.assertFalse(hasattr(result, "authorized"))
        self.assertFalse(hasattr(result, "authorization_granted"))

    def test_position_breach_rejects(self):
        result = Layer6RiskGate(policy(), enabled=True).evaluate(request(stake=2.01))
        self.assertFalse(result.risk_approved)
        self.assertEqual(result.reason, "EXCEEDS_MAX_POSITION_SIZE")

    def test_daily_loss_boundary_trips_kill_switch(self):
        result = Layer6RiskGate(policy(), enabled=True).evaluate(request(daily_pnl=-5.0))
        self.assertFalse(result.risk_approved)
        self.assertEqual(result.reason, "DAILY_LOSS_LIMIT_BREACHED")

    def test_malformed_numeric_inputs_reject_without_raising(self):
        gate = Layer6RiskGate(policy(), enabled=True)
        for bad in (None, True, "1", float("nan"), float("inf"), -float("inf"), 10**10000):
            with self.subTest(value=type(bad).__name__):
                result = gate.evaluate(request(stake=bad))
                self.assertFalse(result.risk_approved)
                self.assertEqual(result.reason, "INVALID_STAKE")

    def test_exposure_breach_rejects(self):
        result = Layer6RiskGate(policy(), enabled=True).evaluate(
            request(existing_exposure=4.25, stake=1.0)
        )
        self.assertFalse(result.risk_approved)
        self.assertEqual(result.reason, "EXCEEDS_TOTAL_EXPOSURE_LIMIT")

    def test_unknown_state_and_active_kill_switch_reject(self):
        gate = Layer6RiskGate(policy(), enabled=True)
        self.assertEqual(gate.evaluate(request(state_verified=False)).reason, "RISK_STATE_UNVERIFIED")
        self.assertEqual(gate.evaluate(request(account_verified=False)).reason, "ACCOUNT_UNVERIFIED")
        self.assertEqual(gate.evaluate(request(kill_switch_active=True)).reason, "KILL_SWITCH_ACTIVE")

    def test_exception_fails_closed(self):
        class BrokenGate(Layer6RiskGate):
            def _evaluate_checks(self, candidate):
                raise RuntimeError("simulated state-store failure")

        result = BrokenGate(policy(), enabled=True).evaluate(request())
        self.assertFalse(result.risk_approved)
        self.assertEqual(result.reason, "EXCEPTION_FAIL_CLOSED")

    def test_slow_evaluation_fails_closed(self):
        class SlowGate(Layer6RiskGate):
            def _evaluate_checks(self, candidate):
                time.sleep(0.1)
                return super()._evaluate_checks(candidate)

        result = SlowGate(policy(timeout_ms=50), enabled=True).evaluate(request())
        self.assertFalse(result.risk_approved)
        self.assertEqual(result.reason, "TIMEOUT_FAIL_CLOSED")
        self.assertGreater(result.latency_ms, 50.0)

    def test_disabled_by_default_fails_closed(self):
        result = Layer6RiskGate(policy()).evaluate(request())
        self.assertFalse(result.risk_approved)
        self.assertEqual(result.reason, "RISK_GATE_DISABLED")

    def test_invalid_direction_or_blank_symbol_reject(self):
        gate = Layer6RiskGate(policy(), enabled=True)
        self.assertEqual(gate.evaluate(request(direction="")).reason, "INVALID_DIRECTION")
        self.assertEqual(gate.evaluate(request(symbol=" ")).reason, "INVALID_SYMBOL")


if __name__ == "__main__":
    unittest.main()
