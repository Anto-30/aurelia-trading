import unittest
from datetime import datetime, timedelta, timezone

from research.event_driven_macro import (
    Action,
    CompanyExposure,
    EventDrivenMacroEngine,
    MacroRegime,
    MarketSnapshot,
    PoliticalSnapshot,
    ResultStatus,
    Scenario,
    cross_asset_confirmation,
    event_half_life_hours,
    political_risk_score,
    probability_eligible,
    rank_company_exposures,
    scenario_probabilities,
)


class TestEventDrivenMacro(unittest.TestCase):
    def test_hard_probability_policy_no_clipping(self):
        self.assertFalse(probability_eligible(0.54))
        self.assertTrue(probability_eligible(0.55))
        self.assertTrue(probability_eligible(0.75))
        self.assertFalse(probability_eligible(0.76))
        self.assertFalse(probability_eligible(0.82))
        self.assertFalse(probability_eligible(float("nan")))
        self.assertFalse(probability_eligible(float("inf")))

    def test_unresolved_result_is_no_trade(self):
        now = datetime.now(timezone.utc)
        p = PoliticalSnapshot(0.6, 0.5, as_of_utc=now)
        c = PoliticalSnapshot(0.7, 0.6, as_of_utc=now)
        m = MarketSnapshot(
            spx_return_pct=1,
            nasdaq_return_pct=1,
            small_cap_return_pct=1,
            two_year_yield_change_bps=-5,
            ten_year_yield_change_bps=-10,
            credit_spread_change_bps=-3,
            vix_change_pct=-8,
            as_of_utc=now,
        )
        d = EventDrivenMacroEngine().evaluate(previous=p, current=c, market=m, now=now)
        self.assertEqual(d.scenario, Scenario.UNRESOLVED)
        self.assertEqual(d.action, Action.NO_TRADE)
        self.assertIn("RESULT_UNRESOLVED_OR_CONTESTED", d.reasons)
        self.assertFalse(d.capital_authority)

    def test_divided_government_risk_on_candidate(self):
        now = datetime.now(timezone.utc)
        previous = PoliticalSnapshot(0.6, 0.4, ResultStatus.LIKELY, ResultStatus.LIKELY, as_of_utc=now)
        current = PoliticalSnapshot(1.0, 0.0, ResultStatus.CONFIRMED, ResultStatus.LIKELY, as_of_utc=now)
        market = MarketSnapshot(
            spx_return_pct=1,
            nasdaq_return_pct=1,
            small_cap_return_pct=0.5,
            two_year_yield_change_bps=-5,
            ten_year_yield_change_bps=-4,
            credit_spread_change_bps=-2,
            vix_change_pct=-12,
            usd_return_pct=-0.2,
            gold_return_pct=0.5,
            oil_return_pct=1.0,
            crypto_return_pct=2.0,
            as_of_utc=now,
        )
        d = EventDrivenMacroEngine().evaluate(previous=previous, current=current, market=market, now=now)
        self.assertEqual(d.scenario, Scenario.DIVIDED_GOVERNMENT)
        self.assertEqual(d.macro_regime, MacroRegime.RISK_ON)
        self.assertEqual(d.action, Action.TRADE_CANDIDATE)
        self.assertIn(("Healthcare", "Broad Market"), d.relative_value)
        self.assertFalse(d.capital_authority)
        self.assertEqual(d.cross_asset["small_cap_relative"], "UNDERPERFORM")
        self.assertEqual(d.cross_asset["gold"], "UP")
        self.assertEqual(d.cross_asset["vix"], "DOWN")

    def test_stale_market_is_blocked(self):
        now = datetime.now(timezone.utc)
        previous = PoliticalSnapshot(0.4, 0.4, ResultStatus.LIKELY, ResultStatus.LIKELY, as_of_utc=now)
        current = PoliticalSnapshot(0.8, 0.7, ResultStatus.CONFIRMED, ResultStatus.CONFIRMED, as_of_utc=now)
        market = MarketSnapshot(
            spx_return_pct=1,
            nasdaq_return_pct=1,
            small_cap_return_pct=1,
            two_year_yield_change_bps=-5,
            ten_year_yield_change_bps=-5,
            credit_spread_change_bps=-2,
            vix_change_pct=-5,
            as_of_utc=now - timedelta(minutes=11),
        )
        d = EventDrivenMacroEngine().evaluate(previous=previous, current=current, market=market, now=now)
        self.assertEqual(d.action, Action.NO_TRADE)
        self.assertIn("MARKET_DATA_STALE", d.reasons)

    def test_insufficient_cross_asset_confirmation_is_no_trade(self):
        now = datetime.now(timezone.utc)
        previous = PoliticalSnapshot(0.5, 0.5, ResultStatus.LIKELY, ResultStatus.LIKELY, as_of_utc=now)
        current = PoliticalSnapshot(0.9, 0.1, ResultStatus.CONFIRMED, ResultStatus.LIKELY, as_of_utc=now)
        market = MarketSnapshot(spx_return_pct=1.0, as_of_utc=now)
        d = EventDrivenMacroEngine().evaluate(previous=previous, current=current, market=market, now=now)
        self.assertEqual(d.action, Action.NO_TRADE)
        self.assertIn("CROSS_ASSET_CONFIRMATION_INSUFFICIENT", d.reasons)

    def test_risk_off_high_surprise_produces_hedge(self):

        now = datetime.now(timezone.utc)
        previous = PoliticalSnapshot(0.0, 0.0, ResultStatus.LIKELY, ResultStatus.LIKELY, as_of_utc=now)
        current = PoliticalSnapshot(0.0, 0.0, ResultStatus.CONFIRMED, ResultStatus.CONFIRMED, as_of_utc=now)
        market = MarketSnapshot(
            spx_return_pct=-2,
            nasdaq_return_pct=-2.5,
            small_cap_return_pct=-3,
            two_year_yield_change_bps=80,
            ten_year_yield_change_bps=90,
            credit_spread_change_bps=25,
            vix_change_pct=30,
            as_of_utc=now,
        )
        d = EventDrivenMacroEngine().evaluate(previous=previous, current=current, market=market, now=now)
        self.assertEqual(d.scenario, Scenario.DEMOCRATIC_SWEEP)
        self.assertEqual(d.macro_regime, MacroRegime.RISK_OFF)
        self.assertEqual(d.action, Action.HEDGE)

    def test_company_exposure_ranking_requires_evidence_and_normalizes_hyphens(self):
        rows = rank_company_exposures(
            [
                CompanyExposure("Acme", "Healthcare", "drug_pricing", 35, "POSITIVE", "filing:123"),
                CompanyExposure("NoEvidence", "Healthcare", "drug_pricing", 90, "POSITIVE", ""),
                CompanyExposure("BadPct", "Healthcare", "drug_pricing", 120, "POSITIVE", "filing:456"),
                CompanyExposure("TechCo", "Non-AI Technology", "antitrust", 40, "POSITIVE", "filing:789"),
            ],
            scenario=Scenario.DEMOCRATIC_SWEEP,
        )
        self.assertEqual([r.company for r in rows], ["Acme"])
        divided = rank_company_exposures(
            [CompanyExposure("TechCo", "Non-AI Technology", "antitrust", 40, "POSITIVE", "filing:789")],
            scenario=Scenario.DIVIDED_GOVERNMENT,
        )
        self.assertEqual([r.company for r in divided], ["TechCo"])

    def test_invalid_probabilities_are_no_trade(self):
        now = datetime.now(timezone.utc)
        previous = PoliticalSnapshot(0.6, 0.6, ResultStatus.LIKELY, ResultStatus.LIKELY, as_of_utc=now)
        current = PoliticalSnapshot(float("nan"), 0.6, ResultStatus.CONFIRMED, ResultStatus.CONFIRMED, as_of_utc=now)
        market = MarketSnapshot(
            spx_return_pct=1,
            nasdaq_return_pct=1,
            small_cap_return_pct=1,
            two_year_yield_change_bps=-5,
            ten_year_yield_change_bps=-5,
            credit_spread_change_bps=-2,
            vix_change_pct=-5,
            as_of_utc=now,
        )
        d = EventDrivenMacroEngine().evaluate(previous=previous, current=current, market=market, now=now)
        self.assertEqual(d.action, Action.NO_TRADE)
        self.assertIn("CURRENT_POLITICAL_PROBABILITY_INVALID", d.reasons)

    def test_cross_asset_summary_covers_non_equity_inputs(self):
        m = MarketSnapshot(
            spx_return_pct=1.0,
            small_cap_return_pct=1.5,
            usd_return_pct=-1.0,
            gold_return_pct=2.0,
            oil_return_pct=-2.0,
            crypto_return_pct=3.0,
            two_year_yield_change_bps=10,
            ten_year_yield_change_bps=-5,
            credit_spread_change_bps=-4,
            vix_change_pct=-7,
        )
        c = cross_asset_confirmation(m)
        self.assertEqual(c["small_cap_relative"], "OUTPERFORM")
        self.assertEqual(c["usd"], "DOWN")
        self.assertEqual(c["gold"], "UP")
        self.assertEqual(c["oil"], "DOWN")
        self.assertEqual(c["crypto"], "UP")
        self.assertEqual(c["credit_spreads"], "TIGHTER")

    def test_risk_score_and_trade_expression_are_deterministic(self):
        self.assertEqual(
            political_risk_score(
                surprise_score=60,
                scenario=Scenario.DIVIDED_GOVERNMENT,
                regime=MacroRegime.RISK_ON,
                contested=False,
            ),
            30.0,
        )
        now = datetime.now(timezone.utc)
        d = EventDrivenMacroEngine().evaluate(
            previous=PoliticalSnapshot(0.0, 0.0, ResultStatus.LIKELY, ResultStatus.LIKELY, as_of_utc=now),
            current=PoliticalSnapshot(1.0, 0.2, ResultStatus.CONFIRMED, ResultStatus.LIKELY, as_of_utc=now),
            market=MarketSnapshot(
                spx_return_pct=1,
                nasdaq_return_pct=1,
                small_cap_return_pct=1,
                two_year_yield_change_bps=-5,
                ten_year_yield_change_bps=-4,
                credit_spread_change_bps=-2,
                vix_change_pct=-12,
                as_of_utc=now,
            ),
            now=now,
        )
        self.assertIn("DEFINED_RISK_CALL_SPREAD", d.trade_expressions)

    def test_event_half_life_is_explicit(self):
        self.assertEqual(event_half_life_hours("ELECTION_RESULT"), 120)
        self.assertEqual(event_half_life_hours("FED_DECISION"), 48)
        self.assertEqual(event_half_life_hours("TARIFF_ACTION"), 720)
        self.assertEqual(event_half_life_hours("UNKNOWN_EVENT"), 168)

    def test_scenario_priors_sum_to_one(self):
        snapshot = PoliticalSnapshot(
            0.70,
            0.40,
            as_of_utc=datetime.now(timezone.utc),
        )
        priors = scenario_probabilities(snapshot)
        self.assertAlmostEqual(sum(priors.values()), 1.0)
        self.assertAlmostEqual(priors[Scenario.DIVIDED_GOVERNMENT], 0.54)


if __name__ == "__main__":
    unittest.main()
