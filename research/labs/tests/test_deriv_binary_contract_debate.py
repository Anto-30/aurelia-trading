from __future__ import annotations

import unittest

from research.labs.deriv_binary_contract_debate import (
    ContractProposal, evaluate_contract,
)


def proposal(**changes):
    values = dict(
        symbol="R_100", direction="CALL", stake=1.0,
        total_return_if_won=1.85, estimated_win_probability=0.60,
        probability_lower_bound=0.58, quote_age_ms=50,
        payout_change_pct_500ms=0.2, equity=100.0, drawdown_pct=0.0,
        consecutive_losses=0, calibration_valid=True,
        out_of_sample_qualified=True,
    )
    values.update(changes)
    return ContractProposal(**values)


class DerivBinaryContractDebateTests(unittest.TestCase):
    def test_positive_ev_uses_conservative_probability_bound(self):
        result = evaluate_contract(proposal())
        self.assertEqual(result.action, "RESEARCH_APPROVED")
        self.assertAlmostEqual(result.break_even_probability, 1 / 1.85)
        self.assertAlmostEqual(result.expected_value_cash, 0.58 * 0.85 - 0.42)
        self.assertLessEqual(result.maximum_stake, 1.0)
        self.assertIn("NO_ORDER_SUBMISSION", result.checks)

    def test_negative_ev_rejected(self):
        result = evaluate_contract(proposal(estimated_win_probability=0.52,
                                           probability_lower_bound=0.52))
        self.assertEqual(result.action, "REJECT")
        self.assertIn(result.reason, {"CONSERVATIVE_PROBABILITY_NOT_ABOVE_BREAK_EVEN",
                                      "EXPECTED_VALUE_BUFFER_NOT_MET"})

    def test_stale_or_unstable_quote_waits(self):
        self.assertEqual(evaluate_contract(proposal(quote_age_ms=501)).action, "WAIT")
        self.assertEqual(evaluate_contract(proposal(payout_change_pct_500ms=2.1)).action, "WAIT")

    def test_missing_calibration_or_oos_blocks(self):
        self.assertEqual(evaluate_contract(proposal(calibration_valid=False)).reason,
                         "PROBABILITY_CALIBRATION_UNVERIFIED")
        self.assertEqual(evaluate_contract(proposal(out_of_sample_qualified=False)).reason,
                         "OUT_OF_SAMPLE_QUALIFICATION_MISSING")

    def test_drawdown_and_loss_streak_breakers(self):
        self.assertEqual(evaluate_contract(proposal(drawdown_pct=0.03)).reason,
                         "DRAWDOWN_CIRCUIT_BREAKER")
        self.assertEqual(evaluate_contract(proposal(consecutive_losses=3)).reason,
                         "CONSECUTIVE_LOSS_CIRCUIT_BREAKER")

    def test_nan_and_invalid_payout_fail_closed(self):
        self.assertEqual(evaluate_contract(proposal(equity=float("nan"))).reason,
                         "INVALID_NUMERIC:equity")
        self.assertEqual(evaluate_contract(proposal(total_return_if_won=1.0)).reason,
                         "CONTRACT_PAYOUT_INVALID")

    def test_stake_must_fit_both_kelly_and_equity_cap(self):
        # Preserve valid contract economics while proposing a stake above the cap.
        result = evaluate_contract(proposal(stake=5.0, total_return_if_won=9.25))
        self.assertEqual(result.action, "REJECT")
        self.assertEqual(result.reason, "PROPOSED_STAKE_EXCEEDS_RISK_CAP")

    def test_probability_interval_must_be_ordered(self):
        self.assertEqual(evaluate_contract(proposal(probability_lower_bound=0.61)).reason,
                         "PROBABILITY_INTERVAL_INVALID")


if __name__ == "__main__":
    unittest.main()
