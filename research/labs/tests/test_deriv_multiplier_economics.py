from datetime import datetime, timezone, timedelta
from decimal import Decimal
import unittest

from research.labs.deriv_multiplier_economics import (
    ObservedMultiplierQuote,
    evaluate_multiplier_economics,
    multiplier_opening_commission,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64
NOW = datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc)


def evaluate(quote, **overrides):
    contract_type = quote.contract_type.upper()
    defaults = {
        "account_equity": "100",
        "available_balance": "100",
        "account_currency": "USD",
        "account_captured_at_utc": NOW.isoformat(),
        "account_snapshot_sha256": HASH_C,
        "account_reference_sha256": HASH_D,
        "stop_execution_price": "9990" if contract_type == "MULTUP" else "10010",
        "target_execution_price": "10030" if contract_type == "MULTUP" else "9960",
        "slippage_evidence_sha256": HASH_E,
        "broker_stop_loss_mapped_price": overrides.get(
            "stop_price", "9990" if contract_type == "MULTUP" else "10010"
        ),
        "broker_take_profit_mapped_price": overrides.get(
            "target_price", "10030" if contract_type == "MULTUP" else "9960"
        ),
        "broker_mapping_sha256": HASH_B,
        "as_of_utc": NOW,
    }
    defaults.update(overrides)
    return evaluate_multiplier_economics(quote, **defaults)


def quote(**overrides):
    data = dict(
        symbol="R_100",
        contract_type="MULTUP",
        currency="USD",
        proposal_id="proposal-evidence-only",
        stake="1.00",
        multiplier="100",
        entry_spot="10000",
        commission="0.02",
        minimum_stake="1.00",
        price_increment="0.01",
        observed_at_utc=NOW.isoformat(),
        catalogue_sha256=HASH_A,
        proposal_sha256=HASH_B,
    )
    data.update(overrides)
    return ObservedMultiplierQuote(**data)


class DerivMultiplierEconomicsTests(unittest.TestCase):
    def test_commission_percent_applies_to_stake_times_multiplier_with_floor(self):
        self.assertEqual(
            multiplier_opening_commission(
                stake="20",
                multiplier="2",
                commission_rate_percent="0.1",
                minimum_commission="0.10",
            ),
            Decimal("0.10"),
        )

    def test_commission_percentage_above_floor_is_not_treated_as_cash_amount(self):
        self.assertEqual(
            multiplier_opening_commission(
                stake="200",
                multiplier="5",
                commission_rate_percent="0.036",
                minimum_commission="0.10",
            ),
            Decimal("0.36000"),
        )

    def test_missing_or_negative_minimum_commission_fails_closed(self):
        for value in (None, "-0.01"):
            with self.assertRaises(ValueError):
                multiplier_opening_commission(
                    stake="20",
                    multiplier="2",
                    commission_rate_percent="0.1",
                    minimum_commission=value,
                )

    def test_up_prices_calculate_net_contract_pnl_and_three_r(self):
        result = evaluate(
            quote(), stop_price="9990", target_price="10030",
            account_equity="100", available_balance="100", as_of_utc=NOW,
        )
        self.assertTrue(result.model_valid)
        self.assertFalse(result.executable)
        self.assertFalse(result.risk_gate_passed)
        self.assertEqual(Decimal(result.gross_stop_pnl), Decimal("-0.10"))
        self.assertEqual(Decimal(result.net_stop_pnl), Decimal("-0.12"))
        self.assertEqual(Decimal(result.net_target_pnl), Decimal("0.28"))
        self.assertIn("NET_REWARD_RISK_BELOW_REQUIRED_MINIMUM", result.blockers)

    def test_down_prices_invert_direction_correctly(self):
        result = evaluate(
            quote(contract_type="MULTDOWN"),
            stop_price="10010", target_price="9960",
            account_equity="100", available_balance="100", risk_fraction="0.02",
            minimum_net_reward_risk="2.0", as_of_utc=NOW,
        )
        self.assertTrue(result.model_valid)
        self.assertTrue(result.risk_gate_passed)
        self.assertLess(Decimal(result.net_stop_pnl), 0)
        self.assertGreater(Decimal(result.net_target_pnl), 0)

    def test_stale_quote_blocks(self):
        result = evaluate(
            quote(observed_at_utc=(NOW - timedelta(seconds=31)).isoformat()),
            stop_price="9990", target_price="10050",
            account_equity="100", available_balance="100", as_of_utc=NOW,
        )
        self.assertIn("QUOTE_STALE_OR_FROM_FUTURE", result.blockers)
        self.assertFalse(result.risk_gate_passed)

    def test_missing_minimum_stake_blocks_even_if_formula_is_valid(self):
        result = evaluate(
            quote(minimum_stake=None), stop_price="9990", target_price="10050",
            account_equity="100", available_balance="100", as_of_utc=NOW,
        )
        self.assertIn("MINIMUM_STAKE_NOT_VERIFIED_FROM_ACCOUNT_PRODUCT", result.blockers)
        self.assertFalse(result.risk_gate_passed)

    def test_stop_at_or_beyond_stake_cap_blocks(self):
        result = evaluate(
            quote(multiplier="1000"), stop_price="9980", target_price="10100",
            stop_execution_price="9980", target_execution_price="10100",
        )
        self.assertIn("STOP_AT_OR_BEYOND_STAKE_STOP_OUT_CAP", result.blockers)

    def test_stake_and_commission_must_fit_risk_budget(self):
        result = evaluate(
            quote(), stop_price="9990", target_price="10050",
            account_equity="50", available_balance="50", risk_fraction="0.01",
            minimum_net_reward_risk="1.0", as_of_utc=NOW,
        )
        self.assertIn("STAKE_PLUS_COMMISSION_EXCEEDS_RISK_BUDGET", result.blockers)

    def test_nonfinite_and_boolean_inputs_fail_closed(self):
        for invalid in ("NaN", "Infinity", True, None):
            result = evaluate(
                quote(stake=invalid), stop_price="9990", target_price="10050",
                account_equity="100", available_balance="100", as_of_utc=NOW,
            )
            self.assertFalse(result.model_valid)
            self.assertFalse(result.executable)

    def test_wrong_side_price_levels_fail_closed(self):
        result = evaluate(
            quote(), stop_price="10010", target_price="10050",
            account_equity="100", available_balance="100", as_of_utc=NOW,
        )
        self.assertIn("MULTUP_PRICE_LEVELS_INVALID", result.blockers)

    def test_exact_three_net_r_is_eligible_when_all_other_gates_pass(self):
        result = evaluate(
            quote(), stop_price="9990", target_price="10038",
            stop_execution_price="9990", target_execution_price="10038",
            account_equity="100", available_balance="100", risk_fraction="0.02",
            minimum_net_reward_risk="3.0",
        )
        self.assertTrue(result.model_valid)
        self.assertTrue(result.risk_gate_passed)
        self.assertEqual(Decimal(result.net_reward_risk), Decimal("3"))
        self.assertFalse(result.executable)

    def test_unverified_price_increment_blocks(self):
        result = evaluate(
            quote(price_increment=None), stop_price="9990", target_price="10050",
            account_equity="100", available_balance="100", risk_fraction="0.02",
            minimum_net_reward_risk="1.0", as_of_utc=NOW,
        )
        self.assertIn("PRICE_INCREMENT_NOT_VERIFIED_FROM_LIVE_INSTRUMENT", result.blockers)

    def test_prices_must_align_to_verified_increment(self):
        result = evaluate(
            quote(), stop_price="9990.005", target_price="10050",
            account_equity="100", available_balance="100", risk_fraction="0.02",
            minimum_net_reward_risk="1.0", as_of_utc=NOW,
        )
        self.assertIn("PRICE_LEVEL_NOT_ALIGNED_TO_VERIFIED_INCREMENT", result.blockers)


    def test_account_currency_must_match_quote_currency(self):
        result = evaluate(
            quote(), stop_price="9990", target_price="10050",
            account_currency="EUR",
        )
        self.assertIn("ACCOUNT_AND_CONTRACT_CURRENCY_MISMATCH", result.blockers)
        self.assertFalse(result.risk_gate_passed)

    def test_stale_account_snapshot_blocks(self):
        stale = (NOW - timedelta(seconds=16)).isoformat()
        result = evaluate(
            quote(), stop_price="9990", target_price="10050",
            account_captured_at_utc=stale,
        )
        self.assertIn("ACCOUNT_CAPITAL_SNAPSHOT_STALE_OR_FROM_FUTURE", result.blockers)
        self.assertFalse(result.risk_gate_passed)

    def test_broker_returned_mapping_must_match_intended_levels(self):
        result = evaluate(
            quote(), stop_price="9990", target_price="10050",
            broker_stop_loss_mapped_price="9980",
            broker_take_profit_mapped_price="10050",
        )
        self.assertIn("BROKER_STOP_MAPPING_OUTSIDE_ONE_TICK_TOLERANCE", result.blockers)
        self.assertFalse(result.risk_gate_passed)

    def test_broker_mapping_within_one_increment_is_accepted(self):
        result = evaluate(
            quote(), stop_price="9990", target_price="10050",
            broker_stop_loss_mapped_price="9990.01",
            broker_take_profit_mapped_price="10049.99",
            risk_fraction="0.02", minimum_net_reward_risk="1.0",
        )
        self.assertTrue(result.model_valid)
        self.assertTrue(result.risk_gate_passed)

    def test_non_adverse_slippage_assumption_blocks(self):
        result = evaluate(
            quote(), stop_price="9990", target_price="10050",
            stop_execution_price="9995",
        )
        self.assertIn(
            "MULTUP_SLIPPAGE_INPUT_NOT_ADVERSE_CONSERVATIVE", result.blockers
        )
        self.assertFalse(result.risk_gate_passed)

    def test_invalid_account_evidence_hash_blocks(self):
        result = evaluate(
            quote(), stop_price="9990", target_price="10050",
            account_snapshot_sha256="invalid",
        )
        self.assertIn("ACCOUNT_SNAPSHOT_HASH_INVALID", result.blockers)
        self.assertFalse(result.risk_gate_passed)

    def test_invalid_evidence_hash_fails_closed(self):
        result = evaluate(
            quote(proposal_sha256="not-a-hash"),
            stop_price="9990", target_price="10050",
            account_equity="100", available_balance="100", as_of_utc=NOW,
        )
        self.assertIn("PROPOSAL_EVIDENCE_HASH_INVALID", result.blockers)


if __name__ == "__main__":
    unittest.main()
