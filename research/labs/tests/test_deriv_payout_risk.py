from __future__ import annotations

import random
import unittest

from research.labs.deriv_payout_risk import (
    AccountRiskSnapshot,
    ContractQuote,
    CriticConfig,
    DebateAction,
    TradeProposal,
    break_even_probability,
    evaluate_debate,
    expected_value,
    realized_reward,
)


def fixture(*, ask=10.0, payout=18.5, proposer=0.60, critic=0.60, lower=0.60,
            vol=0.50, quote_age=10.0, payout_drop=0.0, elapsed=5.0,
            calibrated=True, equity=1000.0, peak=1000.0, losses=0,
            account_age=10.0, verified=True, additional_cost=0.0):
    quote = ContractQuote(
        symbol="R_100", contract_type="CALL", currency="USD", ask_price=ask,
        payout_total=payout, proposal_id="synthetic-quote-id", quote_age_ms=quote_age,
        payout_drop_fraction=payout_drop,
    )
    proposal = TradeProposal(
        quote=quote, proposer_probability=proposer, critic_probability=critic,
        confidence_lower_bound=lower, calibrated=calibrated,
        volatility_percentile=vol, debate_elapsed_ms=elapsed,
        additional_cost=additional_cost,
    )
    account = AccountRiskSnapshot(
        equity=equity, daily_peak_equity=peak, consecutive_losses=losses,
        currency="USD", age_ms=account_age, verified=verified,
    )
    return proposal, account


class DerivPayoutRiskTests(unittest.TestCase):
    def test_example_break_even_and_ev_are_hand_calculated(self):
        self.assertAlmostEqual(break_even_probability(ask_price=10, payout_total=18.5), 10 / 18.5)
        self.assertAlmostEqual(expected_value(ask_price=10, payout_total=18.5, win_probability=0.55), 0.175)
        p, a = fixture(proposer=0.55, critic=0.55, lower=0.55)
        decision = evaluate_debate(p, a)
        self.assertEqual(decision.action, DebateAction.REJECT)
        self.assertEqual(decision.reasons, ("EV_BELOW_REQUIRED_BUFFER",))
        self.assertAlmostEqual(decision.ev_per_risk_dollar, 0.0175)

    def test_ev_equal_to_minimum_buffer_is_rejected(self):
        # For an 85% net win, p=1.02/1.85 produces exactly 2% EV per risk dollar.
        probability = 1.02 / 1.85
        p, a = fixture(ask=10, payout=18.5, proposer=probability,
                       critic=probability, lower=probability)
        self.assertEqual(evaluate_debate(p, a).action, DebateAction.REJECT)

    def test_below_minimum_stake_quote_is_rejected(self):
        p, a = fixture(ask=.5, payout=.925)
        self.assertIn("QUOTE_BELOW_MINIMUM_STAKE", evaluate_debate(p, a).reasons)

    def test_positive_ev_capped_stake_passes_research_gate_only(self):
        p, a = fixture(ask=10, payout=18.5, proposer=.60, critic=.60, lower=.60)
        decision = evaluate_debate(p, a)
        self.assertEqual(decision.action, DebateAction.APPROVE_RESEARCH_ONLY)
        self.assertEqual(decision.recommended_stake_for_requote, 10.0)
        self.assertFalse(decision.capital_authority)
        self.assertFalse(decision.order_submission_permitted)

    def test_kelly_cap_requires_a_new_quote_not_reuse_of_old_proposal(self):
        p, a = fixture(ask=25, payout=46.25, equity=1000, peak=1000)
        decision = evaluate_debate(p, a)
        self.assertEqual(decision.action, DebateAction.WAIT)
        self.assertEqual(decision.recommended_stake_for_requote, 10.0)
        self.assertIn("REQUOTE_AT_RECOMMENDED_STAKE_AND_REEVALUATE", decision.reasons)

    def test_negative_ev_is_rejected(self):
        p, a = fixture(proposer=.52, critic=.52, lower=.52)
        self.assertEqual(evaluate_debate(p, a).action, DebateAction.REJECT)

    def test_critic_uses_conservative_probability_and_rejects_disagreement(self):
        p, a = fixture(proposer=.68, critic=.55, lower=.54)
        decision = evaluate_debate(p, a)
        self.assertEqual(decision.action, DebateAction.REJECT)
        self.assertIn("PROBABILITY_DISAGREEMENT_TOO_WIDE", decision.reasons)

    def test_no_clipping_out_of_policy_probability_is_rejected(self):
        for prob in (.499, .751, .82, float("nan"), float("inf")):
            with self.subTest(prob=prob):
                p, a = fixture(proposer=prob, critic=.60, lower=.55)
                self.assertEqual(evaluate_debate(p, a).action, DebateAction.REJECT)

    def test_high_volatility_and_payout_decay_are_rejected(self):
        p, a = fixture(vol=.95)
        self.assertIn("VOLATILITY_REGIME_OUT_OF_TRAINING_ENVELOPE", evaluate_debate(p, a).reasons)
        p, a = fixture(payout_drop=.011)
        self.assertIn("PAYOUT_MOVED_BEYOND_TOLERANCE", evaluate_debate(p, a).reasons)

    def test_stale_quote_late_debate_unverified_or_stale_account_rejected(self):
        for changes, reason in [
            ({"quote_age": 50.0}, "QUOTE_STALE"),
            ({"elapsed": 50.0}, "DEBATE_DEADLINE_EXCEEDED"),
            ({"verified": False}, "ACCOUNT_SNAPSHOT_UNVERIFIED"),
            ({"account_age": 5001}, "ACCOUNT_SNAPSHOT_STALE"),
        ]:
            with self.subTest(changes=changes):
                p, a = fixture(**changes)
                self.assertIn(reason, evaluate_debate(p, a).reasons)

    def test_daily_drawdown_and_consecutive_losses_trip_circuit_breakers(self):
        p, a = fixture(equity=970, peak=1000)
        self.assertIn("DAILY_DRAWDOWN_CIRCUIT_BREAKER", evaluate_debate(p, a).reasons)
        p, a = fixture(losses=3)
        self.assertIn("CONSECUTIVE_LOSS_CIRCUIT_BREAKER", evaluate_debate(p, a).reasons)

    def test_uncalibrated_probability_model_is_rejected(self):
        p, a = fixture(calibrated=False)
        self.assertIn("PROBABILITY_MODEL_UNCALIBRATED", evaluate_debate(p, a).reasons)

    def test_quote_price_and_account_currency_must_match_supported_currency(self):
        p, a = fixture()
        p = TradeProposal(**{**p.__dict__, "quote": ContractQuote(**{**p.quote.__dict__, "currency": "EUR"})})
        self.assertIn("QUOTE_CURRENCY_NOT_SUPPORTED", evaluate_debate(p, a).reasons)
        p, a = fixture()
        a = AccountRiskSnapshot(**{**a.__dict__, "currency": "EUR"})
        self.assertIn("ACCOUNT_CURRENCY_NOT_SUPPORTED", evaluate_debate(p, a).reasons)

    def test_10k_random_scenarios_never_pass_when_probability_at_or_below_break_even(self):
        rng = random.Random(20261017)
        for _ in range(10_000):
            ask = rng.uniform(1.0, 50.0)
            payout = ask * rng.uniform(1.001, 3.0)
            threshold = ask / payout
            prob = rng.uniform(0.01, min(1.0, threshold))
            # The probability policy band may reject independently; either way, no approve.
            p, a = fixture(ask=ask, payout=payout, proposer=prob, critic=prob, lower=prob, equity=10000, peak=10000)
            self.assertNotEqual(evaluate_debate(p, a).action, DebateAction.APPROVE_RESEARCH_ONLY)

    def test_realized_reward_uses_outcome_not_predicted_probability(self):
        self.assertAlmostEqual(realized_reward(ask_price=10, payout_total=18.5, won=True, equity_before=100), .085)
        self.assertAlmostEqual(realized_reward(ask_price=10, payout_total=18.5, won=False, equity_before=100), -.10)

    def test_policy_configuration_cannot_weaken_hard_caps(self):
        for cfg, expected in [
            (CriticConfig(max_trade_risk_fraction=.02), "CONFIG_MAX_TRADE_RISK_FRACTION_INVALID"),
            (CriticConfig(min_ev_per_risk_dollar=0.0), "CONFIG_MIN_EV_INVALID"),
            (CriticConfig(max_quote_age_ms=51), "CONFIG_QUOTE_AGE_INVALID"),
            (CriticConfig(max_debate_elapsed_ms=51), "CONFIG_DEBATE_LATENCY_INVALID"),
            (CriticConfig(max_payout_drop_fraction=.02), "CONFIG_PAYOUT_DROP_TOLERANCE_INVALID"),
            (CriticConfig(max_consecutive_losses=4), "CONFIG_MAX_CONSECUTIVE_LOSSES_INVALID"),
            (CriticConfig(minimum_stake=.01), "CONFIG_MINIMUM_STAKE_INVALID"),
            (CriticConfig(stake_currency="EUR"), "CONFIG_STAKE_CURRENCY_UNSUPPORTED"),
        ]:
            with self.subTest(config=cfg):
                p, a = fixture()
                self.assertIn(expected, evaluate_debate(p, a, config=cfg).reasons)

    def test_malformed_types_and_huge_integers_fail_closed_without_throwing(self):
        p, a = fixture()
        q = ContractQuote(**{**p.quote.__dict__, "symbol": None})
        p = TradeProposal(**{**p.__dict__, "quote": q})
        self.assertEqual(evaluate_debate(p, a).action, DebateAction.REJECT)
        p, a = fixture()
        a = AccountRiskSnapshot(**{**a.__dict__, "verified": "yes"})
        self.assertIn("ACCOUNT_SNAPSHOT_UNVERIFIED", evaluate_debate(p, a).reasons)
        from research.labs.deriv_payout_risk import _number
        self.assertFalse(_number(10**10000))

    def test_invalid_economics_fail_closed(self):
        for args in [
            {"ask_price": 0, "payout_total": 2, "win_probability": .7},
            {"ask_price": 1, "payout_total": float("nan"), "win_probability": .7},
            {"ask_price": 1, "payout_total": 2, "win_probability": float("inf")},
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                expected_value(**args)


if __name__ == "__main__":
    unittest.main()
