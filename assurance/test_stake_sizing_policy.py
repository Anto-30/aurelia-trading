from __future__ import annotations

import math
import unittest

from runtime.core.authority import (
    MAX_PROBABILITY,
    MIN_PROBABILITY,
    authorization_gate,
    build_intent,
    probability_is_valid,
)
from runtime.core.models import AccountIdentity, CapitalSnapshot, Decision, utc_now
from runtime.core.stake_sizing import size_stake_for_balance


class StakeSizingPolicyTests(unittest.TestCase):
    def test_minimum_balance_funds_one_unit_stake_at_one_percent(self):
        result = size_stake_for_balance(100.00)
        self.assertTrue(result.allowed)
        self.assertEqual(result.stake, 1.00)

    def test_stake_scales_with_verified_available_balance(self):
        balances = [100.00, 150.00, 200.00, 350.99]
        stakes = [size_stake_for_balance(balance).stake for balance in balances]
        self.assertEqual(stakes, [1.00, 1.50, 2.00, 3.50])
        self.assertEqual(stakes, sorted(stakes))

    def test_risk_budget_below_minimum_fails_closed(self):
        for balance in (0.00, 1.50, 50.00, 99.99):
            with self.subTest(balance=balance):
                result = size_stake_for_balance(balance)
                self.assertFalse(result.allowed)
                self.assertIsNone(result.stake)
                self.assertEqual(result.reason, "STAKE_RISK_BUDGET_BELOW_BROKER_MINIMUM")

    def test_risk_budget_is_rounded_down_to_cents(self):
        result = size_stake_for_balance(234.567)
        self.assertTrue(result.allowed)
        self.assertEqual(result.stake, 2.34)

    def test_invalid_balance_and_risk_fraction_are_rejected(self):
        for balance in (True, -1, float("nan"), float("inf"), "100"):
            with self.subTest(balance=balance):
                self.assertFalse(size_stake_for_balance(balance).allowed)
        self.assertFalse(size_stake_for_balance(100, maximum_risk_fraction=0.03).allowed)

    def test_probability_band_is_50_to_75_percent_without_clipping(self):
        self.assertEqual(MIN_PROBABILITY, 0.50)
        self.assertEqual(MAX_PROBABILITY, 0.75)
        self.assertTrue(probability_is_valid(0.50))
        self.assertTrue(probability_is_valid(0.75))
        self.assertFalse(probability_is_valid(0.4999))
        self.assertFalse(probability_is_valid(0.7501))
        self.assertFalse(probability_is_valid(float("nan")))
        self.assertFalse(probability_is_valid(float("inf")))

    def test_live_authorization_uses_balance_scaled_stake(self):
        account = AccountIdentity(
            loginid="CR123456",
            account_type="real",
            currency="USD",
            environment="real",
        )
        capital = CapitalSnapshot(
            balance=200.00,
            currency="USD",
            available_balance=200.00,
            captured_at=utc_now(),
            source="verified-test-snapshot",
            account=account,
        )
        decision = Decision(
            decision_id="sizing-test-1",
            strategy_id="test-strategy",
            strategy_version="1",
            strategy_hash="sha256:test-strategy",
            symbol="TEST",
            direction="CALL",
            probability=0.60,
            decision_time=utc_now(),
            market_snapshot_hash="sha256:test-market",
            risk_requested_stake=1.00,
            average_win=2.00,
            average_loss=1.00,
        )
        gate, context = authorization_gate(
            decision=decision,
            account=account,
            capital=capital,
            config_hash="config-digest",
            runtime_config_hash="config-digest",
            kill_switch_off=True,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=True,
            live_trading_enabled=True,
            probability_calibrated=True,
            probability_fresh=True,
            probability_drift_ok=True,
            market_data_validated=True,
            exposure_approved=True,
            execution_mode="LIVE",
        )
        self.assertTrue(gate.allowed, gate.reason_codes)
        self.assertIsNotNone(context)
        intent = build_intent(context, proposal_id="proposal-test")
        self.assertEqual(intent.stake, 2.00)

    def test_live_authorization_requires_verified_usd_account(self):
        account = AccountIdentity("CR123456", "real", "EUR", "real")
        capital = CapitalSnapshot(
            balance=200.00,
            currency="EUR",
            available_balance=200.00,
            captured_at=utc_now(),
            source="verified-test-snapshot",
            account=account,
        )
        decision = Decision(
            decision_id="sizing-test-eur",
            strategy_id="test-strategy",
            strategy_version="1",
            strategy_hash="sha256:test-strategy",
            symbol="TEST",
            direction="CALL",
            probability=0.60,
            decision_time=utc_now(),
            market_snapshot_hash="sha256:test-market",
            risk_requested_stake=1.00,
            average_win=2.00,
            average_loss=1.00,
        )
        gate, context = authorization_gate(
            decision=decision,
            account=account,
            capital=capital,
            config_hash="config-digest",
            runtime_config_hash="config-digest",
            kill_switch_off=True,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=True,
            live_trading_enabled=True,
            probability_calibrated=True,
            probability_fresh=True,
            probability_drift_ok=True,
            market_data_validated=True,
            exposure_approved=True,
            execution_mode="LIVE",
        )
        self.assertFalse(gate.allowed)
        self.assertIsNone(context)
        self.assertIn("USD_STAKE_POLICY_REQUIRES_USD_ACCOUNT", gate.reason_codes)

    def test_live_authorization_blocks_when_minimum_stake_breaks_one_percent_budget(self):
        account = AccountIdentity("CR123456", "real", "USD", "real")
        capital = CapitalSnapshot(
            balance=99.99,
            currency="USD",
            available_balance=99.99,
            captured_at=utc_now(),
            source="verified-test-snapshot",
            account=account,
        )
        decision = Decision(
            decision_id="sizing-test-2",
            strategy_id="test-strategy",
            strategy_version="1",
            strategy_hash="sha256:test-strategy",
            symbol="TEST",
            direction="CALL",
            probability=0.60,
            decision_time=utc_now(),
            market_snapshot_hash="sha256:test-market",
            risk_requested_stake=1.00,
            average_win=2.00,
            average_loss=1.00,
        )
        gate, context = authorization_gate(
            decision=decision,
            account=account,
            capital=capital,
            config_hash="config-digest",
            runtime_config_hash="config-digest",
            kill_switch_off=True,
            risk_approved=True,
            firewall_approved=True,
            reconciliation_healthy=True,
            final_execution_authorization=True,
            live_trading_enabled=True,
            probability_calibrated=True,
            probability_fresh=True,
            probability_drift_ok=True,
            market_data_validated=True,
            exposure_approved=True,
            execution_mode="LIVE",
        )
        self.assertFalse(gate.allowed)
        self.assertIsNone(context)
        self.assertIn("STAKE_RISK_BUDGET_BELOW_BROKER_MINIMUM", gate.reason_codes)


if __name__ == "__main__":
    unittest.main()
