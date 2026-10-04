import unittest
from datetime import datetime, timezone

from runtime.core.authority import authorization_gate, build_intent
from runtime.core.models import AccountIdentity, CapitalSnapshot, Decision


class VerifyOnlyAuthorityTest(unittest.TestCase):
    def _inputs(self):
        account = AccountIdentity(
            loginid="REAL_TEST",
            account_type="real",
            currency="USD",
            environment="real",
        )
        capital = CapitalSnapshot(
            balance=2.0,
            currency="USD",
            available_balance=2.0,
            captured_at=datetime.now(timezone.utc),
            source="test",
            account=account,
        )
        decision = Decision(
            decision_id="verify-only-test",
            strategy_id="VERIFY_ONLY_BROKER_PLUMBING",
            strategy_version="1",
            strategy_hash="VERIFY_ONLY_BROKER_PLUMBING_V1",
            symbol="R_100",
            direction="BUY",
            probability=0.60,
            decision_time=datetime.now(timezone.utc),
            market_snapshot_hash="snapshot",
            risk_requested_stake=1.0,
            rationale_codes=("VERIFY_ONLY",),
        )
        return account, capital, decision

    def test_verify_only_can_construct_non_live_intent(self):
        account, capital, decision = self._inputs()
        gate, context = authorization_gate(
            decision=decision,
            account=account,
            capital=capital,
            config_hash="cfg",
            runtime_config_hash="cfg",
            kill_switch_off=False,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=False,
            live_trading_enabled=False,
            probability_calibrated=True,
            probability_fresh=True,
            probability_drift_ok=True,
            market_data_validated=True,
            exposure_approved=True,
            execution_mode="VERIFY_ONLY",
        )
        self.assertTrue(gate.allowed, gate.reason_codes)
        self.assertIsNotNone(context)
        intent = build_intent(context, proposal_id="proposal-test", mode="VERIFY_ONLY")
        self.assertEqual(intent.execution_mode, "VERIFY_ONLY")

    def test_live_mode_still_requires_live_authorization(self):
        account, capital, decision = self._inputs()
        gate, context = authorization_gate(
            decision=decision,
            account=account,
            capital=capital,
            config_hash="cfg",
            runtime_config_hash="cfg",
            kill_switch_off=False,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=False,
            live_trading_enabled=False,
            probability_calibrated=True,
            probability_fresh=True,
            probability_drift_ok=True,
            market_data_validated=True,
            exposure_approved=True,
            execution_mode="LIVE",
        )
        self.assertFalse(gate.allowed)
        self.assertIsNone(context)
        self.assertIn("FINAL_EXECUTION_AUTHORIZATION_FALSE", gate.reason_codes)
        self.assertIn("LIVE_TRADING_DISABLED", gate.reason_codes)


if __name__ == "__main__":
    unittest.main()
