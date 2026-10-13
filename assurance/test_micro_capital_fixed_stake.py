from __future__ import annotations

import unittest
from decimal import Decimal

from runtime.core.micro_capital import evaluate_micro_capital_stake


def valid_inputs(**overrides):
    values = {
        "available_balance": "1.45",
        "currency": "USD",
        "account_verified": True,
        "balance_fresh": True,
        "exact_contract_quote_verified": True,
        "quoted_stake": "0.35",
        "quoted_max_loss": "0.35",
        "one_open_contract_or_less": True,
        "session_loss_usd": "0.00",
        "transaction_state_reconciled": True,
        "strategy_qualified": True,
        "probability": "0.60",
        "probability_calibrated": True,
        "probability_fresh": True,
        "probability_drift_ok": True,
        "net_economics_positive": True,
        "kill_switch_clear": True,
        "canonical_release_gate_passed": True,
    }
    values.update(overrides)
    return values


class MicroCapitalPolicyTests(unittest.TestCase):
    def test_valid_inputs_return_exact_035_and_expose_high_risk(self):
        result = evaluate_micro_capital_stake(**valid_inputs())
        self.assertTrue(result.allowed)
        self.assertEqual(result.stake, Decimal("0.35"))
        self.assertAlmostEqual(float(result.loss_fraction), 1 / 1.45, places=6)
        self.assertIn("MICRO_STAKE_POLICY_PASSED_RELEASE_GATE_STILL_REQUIRED", result.reason_codes)

    def test_broker_minimum_above_035_is_not_forced_down(self):
        result = evaluate_micro_capital_stake(**valid_inputs(
            exact_contract_quote_verified=False,
            quoted_stake="0.50",
        ))
        self.assertFalse(result.allowed)
        self.assertIn("EXACT_CONTRACT_QUOTE_UNVERIFIED", result.reason_codes)
        self.assertIn("QUOTED_STAKE_NOT_EXACTLY_USD_0_35", result.reason_codes)

    def test_stale_balance_or_unverified_account_blocks(self):
        result = evaluate_micro_capital_stake(**valid_inputs(
            account_verified=False,
            balance_fresh=False,
        ))
        self.assertFalse(result.allowed)
        self.assertIn("ACCOUNT_UNVERIFIED", result.reason_codes)
        self.assertIn("BALANCE_STALE", result.reason_codes)

    def test_session_loss_cap_blocks_second_full_loss(self):
        result = evaluate_micro_capital_stake(**valid_inputs(session_loss_usd="0.35"))
        self.assertFalse(result.allowed)
        self.assertIn("MICRO_SESSION_LOSS_LIMIT_REACHED", result.reason_codes)

    def test_unqualified_or_uncalibrated_strategy_blocks(self):
        result = evaluate_micro_capital_stake(**valid_inputs(
            strategy_qualified=False,
            probability_calibrated=False,
        ))
        self.assertFalse(result.allowed)
        self.assertIn("STRATEGY_NOT_QUALIFIED", result.reason_codes)
        self.assertIn("PROBABILITY_NOT_CALIBRATED", result.reason_codes)

    def test_probability_outside_inclusive_band_blocks_without_clipping(self):
        for probability in ("0.5499", "0.7501", "0.82"):
            with self.subTest(probability=probability):
                result = evaluate_micro_capital_stake(**valid_inputs(probability=probability))
                self.assertFalse(result.allowed)
                self.assertIn("PROBABILITY_OUTSIDE_HARD_POLICY", result.reason_codes)

    def test_non_usd_or_unaffordable_stake_blocks(self):
        non_usd = evaluate_micro_capital_stake(**valid_inputs(currency="EUR"))
        self.assertFalse(non_usd.allowed)
        self.assertIn("CURRENCY_MISMATCH", non_usd.reason_codes)

        poor_balance = evaluate_micro_capital_stake(**valid_inputs(available_balance="0.34"))
        self.assertFalse(poor_balance.allowed)
        self.assertIn("STAKE_UNAFFORDABLE", poor_balance.reason_codes)

    def test_unknown_transaction_kill_switch_or_live_lock_blocks(self):
        result = evaluate_micro_capital_stake(**valid_inputs(
            transaction_state_reconciled=False,
            kill_switch_clear=False,
            canonical_release_gate_passed=False,
        ))
        self.assertFalse(result.allowed)
        self.assertIn("TRANSACTION_RECONCILIATION_REQUIRED", result.reason_codes)
        self.assertIn("KILL_SWITCH_ACTIVE", result.reason_codes)
        self.assertIn("LIVE_RELEASE_GATE_BLOCKED", result.reason_codes)

    def test_truthy_non_boolean_gate_values_fail_closed(self):
        result = evaluate_micro_capital_stake(**valid_inputs(account_verified="false"))
        self.assertFalse(result.allowed)
        self.assertIn("ACCOUNT_UNVERIFIED", result.reason_codes)

    def test_invalid_values_fail_closed(self):
        for balance in (True, "NaN", "-1", None):
            with self.subTest(balance=balance):
                result = evaluate_micro_capital_stake(**valid_inputs(available_balance=balance))
                self.assertFalse(result.allowed)
                self.assertIn("BALANCE_INVALID", result.reason_codes)


if __name__ == "__main__":
    unittest.main()
