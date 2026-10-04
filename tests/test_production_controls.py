import unittest
from datetime import timedelta
from runtime.core.production_controls import (
    CanaryPolicy, CircuitBreaker, DecisionTimeGate,
    deployment_matches, fresh, post_trade_guard, utc_now,
)

class ProductionControlsTests(unittest.TestCase):
    def test_decision_time_gate_is_conjunctive(self):
        self.assertTrue(DecisionTimeGate(True, True, True, True, True, True, True).passed)
        self.assertFalse(DecisionTimeGate(True, True, True, True, True, True, False).passed)

    def test_stale_evidence_fails(self):
        now = utc_now()
        self.assertTrue(fresh(now - timedelta(seconds=4), 5, now=now))
        self.assertFalse(fresh(now - timedelta(seconds=6), 5, now=now))

    def test_deployment_lineage_requires_both_hash_pairs(self):
        self.assertTrue(deployment_matches(source_hash="a", runtime_source_hash="a", artifact_hash="b", runtime_artifact_hash="b"))
        self.assertFalse(deployment_matches(source_hash="a", runtime_source_hash="c", artifact_hash="b", runtime_artifact_hash="b"))

    def test_circuit_breaker_trips_on_reconciliation(self):
        cb = CircuitBreaker()
        cb.record_reconciliation_failure()
        self.assertTrue(cb.tripped)
        self.assertFalse(cb.permit())

    def test_post_trade_unknown_is_fail_closed(self):
        cb = CircuitBreaker()
        ok, reasons = post_trade_guard(reconciliation_healthy=True, unexpected_balance_delta=False,
                                       slippage_breach=False, broker_status_known=False, circuit=cb)
        self.assertFalse(ok)
        self.assertIn("BROKER_STATUS_UNKNOWN", reasons)

    def test_canary_limits_first_live_trade(self):
        policy = CanaryPolicy(max_trades=1, max_stake=1.0)
        self.assertTrue(policy.permits(trades_completed=0, stake=1.0))
        self.assertFalse(policy.permits(trades_completed=1, stake=1.0))
        self.assertFalse(policy.permits(trades_completed=0, stake=1.01))

if __name__ == "__main__":
    unittest.main()
