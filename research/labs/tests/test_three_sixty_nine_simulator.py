from __future__ import annotations

import unittest
from datetime import datetime, timezone

from research.labs.deterministic_intraday_strategies import StrategyBar
from research.labs.intraday_bias_cost_model import InstrumentCostProfile
from research.labs.three_sixty_nine_msnr import ThreeSixtyNineMSNRCandidate
from research.labs.three_sixty_nine_simulator import simulate_candidate


def _candidate():
    return ThreeSixtyNineMSNRCandidate(
        strategy_id="THREE_SIXTY_NINE_MSNR",
        version="0.1.0",
        instrument_id="TEST_R100",
        direction="LONG",
        signal_close_timestamp_utc="2026-01-05T09:45:00+00:00",
        entry_timestamp_utc="2026-01-05T09:46:00+00:00",
        entry_price=100.0,
        stop_price=99.0,
        target_price=103.0,
        gross_r=3.0,
        variant_id="BASELINE",
        target_selection_rule="TEST",
        evidence_codes=("TEST_ONLY",),
    )


def _bars(*rows):
    return tuple(
        StrategyBar(
            timestamp_utc=f"2026-01-05T09:{46 + index:02d}:00+00:00",
            open=row[0],
            high=row[1],
            low=row[2],
            close=row[3],
        )
        for index, row in enumerate(rows)
    )


def _cost_profile(**overrides):
    values = dict(
        instrument_id="TEST_R100",
        instrument_type="SYNTHETIC_INDEX_UNDERLYING",
        return_basis="UNDERLYING_PRICE_NOTIONAL",
        spread_cost_bps_round_trip=1.0,
        slippage_cost_bps_round_trip=1.0,
        commission_bps_round_trip=0.0,
        other_fees_bps_round_trip=0.0,
        source="synthetic-test-fixture",
        observed_at_utc=datetime.now(timezone.utc).isoformat(),
        verified=True,
        slippage_excludes_spread=True,
    )
    values.update(overrides)
    return InstrumentCostProfile(**values)


class ThreeSixtyNineSimulatorTests(unittest.TestCase):
    def test_entry_is_next_bar_open_and_target_exit_is_three_r(self):
        bars = _bars(
            (100.0, 102.0, 99.5, 101.0),
            (101.0, 104.0, 100.5, 103.0),
        )
        trade = simulate_candidate(
            _candidate(), bars, cost_profile=_cost_profile(), tick_size=0.1
        )
        self.assertIsNotNone(trade)
        self.assertEqual(trade.entry_price, 100.0)
        self.assertEqual(trade.exit_reason, "TAKE_PROFIT")
        self.assertEqual(trade.exit_price, 103.0)
        self.assertAlmostEqual(trade.gross_r, 3.0)
        self.assertFalse(trade.capital_authority)
        self.assertFalse(trade.order_submission_permitted)

    def test_both_stop_and_target_touched_uses_conservative_stop_first(self):
        bars = _bars((100.0, 103.5, 98.5, 101.0))
        trade = simulate_candidate(
            _candidate(), bars, cost_profile=_cost_profile(), tick_size=0.1
        )
        self.assertEqual(trade.exit_reason, "STOP_LOSS")
        self.assertEqual(trade.exit_price, 99.0)
        self.assertAlmostEqual(trade.gross_r, -1.0)

    def test_gap_through_stop_fills_at_adverse_open(self):
        bars = _bars(
            (100.0, 101.0, 99.5, 100.5),
            (98.0, 100.0, 97.5, 99.0),
        )
        trade = simulate_candidate(
            _candidate(), bars, cost_profile=_cost_profile(), tick_size=0.1
        )
        self.assertEqual(trade.exit_reason, "STOP_LOSS")
        self.assertEqual(trade.exit_price, 98.0)
        self.assertAlmostEqual(trade.gross_r, -2.0)

    def test_gap_through_target_does_not_assume_price_improvement(self):
        bars = _bars(
            (100.0, 101.0, 99.5, 100.5),
            (104.0, 105.0, 103.5, 104.5),
        )
        trade = simulate_candidate(
            _candidate(), bars, cost_profile=_cost_profile(), tick_size=0.1
        )
        self.assertEqual(trade.exit_reason, "TAKE_PROFIT")
        self.assertEqual(trade.exit_price, 103.0)

    def test_unknown_costs_block_simulation(self):
        bars = _bars((100.0, 104.0, 99.5, 103.0))
        profile = _cost_profile(slippage_cost_bps_round_trip=None)
        with self.assertRaisesRegex(ValueError, "COST_PROFILE_INVALID"):
            simulate_candidate(_candidate(), bars, cost_profile=profile, tick_size=0.1)

    def test_unresolved_end_of_data_is_not_mislabeled_as_a_trade_exit(self):
        bars = _bars((100.0, 101.0, 99.5, 100.5))
        trade = simulate_candidate(
            _candidate(), bars, cost_profile=_cost_profile(), tick_size=0.1
        )
        self.assertFalse(trade.complete)
        self.assertEqual(trade.exit_reason, "END_OF_DATA")
        self.assertIsNone(trade.exit_price)
        self.assertIsNone(trade.net_r)

    def test_spread_and_slippage_are_separate_cost_components(self):
        bars = _bars((100.0, 104.0, 99.5, 103.0))
        trade = simulate_candidate(
            _candidate(), bars, cost_profile=_cost_profile(), tick_size=0.1
        )
        self.assertGreater(trade.spread_cost, 0)
        self.assertGreater(trade.slippage_cost, 0)
        self.assertEqual(trade.commission_cost, 0)
        self.assertAlmostEqual(
            trade.total_cost,
            trade.spread_cost + trade.slippage_cost + trade.commission_cost + trade.other_fees,
        )


if __name__ == "__main__":
    unittest.main()
