from __future__ import annotations

import unittest
from datetime import datetime, timezone

from research.labs.deterministic_intraday_strategies import StrategyBar
from research.labs.intraday_bias_cost_model import InstrumentCostProfile
from research.labs.three_sixty_nine_msnr import ThreeSixtyNineMSNRCandidate
from research.labs.three_sixty_nine_simulator import simulate_candidate


NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def candidate() -> ThreeSixtyNineMSNRCandidate:
    return ThreeSixtyNineMSNRCandidate(
        strategy_id="THREE_SIXTY_NINE_MSNR",
        version="0.1.0",
        instrument_id="TEST",
        direction="LONG",
        signal_close_timestamp_utc="2026-11-10T10:00:00+00:00",
        entry_timestamp_utc="2026-11-10T10:01:00+00:00",
        entry_price=100.0,
        stop_price=98.0,
        target_price=106.0,
        gross_r=3.0,
        variant_id="BASELINE",
        target_selection_rule="TEST",
        evidence_codes=("TEST",),
    )


def costs(**overrides) -> InstrumentCostProfile:
    values = dict(
        instrument_id="TEST",
        instrument_type="SPOT",
        return_basis="UNDERLYING_PRICE_RETURN",
        spread_cost_bps_round_trip=2.0,
        slippage_cost_bps_round_trip=1.0,
        commission_bps_round_trip=0.5,
        other_fees_bps_round_trip=0.5,
        source="verified-test-statement",
        observed_at_utc="2026-11-10T11:00:00+00:00",
        verified=True,
        slippage_excludes_spread=True,
        max_age_seconds=7200.0,
    )
    values.update(overrides)
    return InstrumentCostProfile(**values)


def bars(*rows) -> tuple[StrategyBar, ...]:
    return tuple(
        StrategyBar(
            timestamp_utc=f"2026-11-10T10:{minute:02d}:00+00:00",
            open=opened,
            high=high,
            low=low,
            close=close,
        )
        for minute, opened, high, low, close in rows
    )


class ThreeSixtyNineSimulatorTests(unittest.TestCase):
    def test_stop_first_when_both_stop_and_target_touched(self):
        trade = simulate_candidate(
            candidate(),
            bars((1, 100.0, 107.0, 97.0, 103.0)),
            cost_profile=costs(),
            tick_size=0.1,
            now=NOW,
        )
        self.assertEqual(trade.exit_reason, "STOP_LOSS")
        self.assertEqual(trade.exit_price, 98.0)

    def test_target_fill_when_only_target_is_touched(self):
        trade = simulate_candidate(
            candidate(),
            bars((1, 100.0, 107.0, 99.0, 105.0)),
            cost_profile=costs(),
            tick_size=0.1,
            now=NOW,
        )
        self.assertEqual(trade.exit_reason, "TAKE_PROFIT")
        self.assertEqual(trade.exit_price, 106.0)

    def test_gap_through_stop_fills_at_worse_open(self):
        trade = simulate_candidate(
            candidate(),
            bars(
                (1, 100.0, 101.0, 99.0, 100.0),
                (2, 95.0, 97.0, 94.0, 96.0),
            ),
            cost_profile=costs(),
            tick_size=0.1,
            now=NOW,
        )
        self.assertEqual(trade.exit_reason, "GAP_THROUGH_STOP")
        self.assertEqual(trade.exit_price, 95.0)

    def test_costs_are_itemized_and_deducted_once(self):
        trade = simulate_candidate(
            candidate(),
            bars((1, 100.0, 101.0, 99.0, 100.5)),
            cost_profile=costs(),
            tick_size=0.1,
            now=NOW,
        )
        self.assertAlmostEqual(trade.spread_cost_per_unit, 0.02)
        self.assertAlmostEqual(trade.slippage_cost_per_unit, 0.01)
        self.assertAlmostEqual(trade.commission_cost_per_unit, 0.005)
        self.assertAlmostEqual(trade.other_fees_per_unit, 0.005)
        self.assertAlmostEqual(trade.total_cost_per_unit, 0.04)
        self.assertAlmostEqual(trade.net_pnl_per_unit, 0.46)
        self.assertFalse(trade.capital_authority)
        self.assertFalse(trade.order_submission_permitted)

    def test_end_of_data_is_explicit_and_uses_last_close(self):
        trade = simulate_candidate(
            candidate(),
            bars((1, 100.0, 101.0, 99.0, 100.5)),
            cost_profile=costs(),
            tick_size=0.1,
            now=NOW,
        )
        self.assertEqual(trade.exit_reason, "END_OF_DATA")
        self.assertEqual(trade.exit_price, 100.5)

    def test_unknown_or_unverified_costs_block_simulation(self):
        for profile in (
            costs(spread_cost_bps_round_trip=None),
            costs(verified=False),
        ):
            with self.subTest(profile=profile):
                with self.assertRaisesRegex(ValueError, "SIMULATOR_COST_PROFILE_INVALID"):
                    simulate_candidate(
                        candidate(),
                        bars((1, 100.0, 101.0, 99.0, 100.5)),
                        cost_profile=profile,
                        tick_size=0.1,
                        now=NOW,
                    )

    def test_stale_cost_profile_blocks_simulation(self):
        with self.assertRaisesRegex(ValueError, "SIMULATOR_COST_PROFILE_INVALID"):
            simulate_candidate(
                candidate(),
                bars((1, 100.0, 101.0, 99.0, 100.5)),
                cost_profile=costs(observed_at_utc="2026-11-01T00:00:00+00:00"),
                tick_size=0.1,
                now=NOW,
            )

    def test_entry_must_match_next_bar_open(self):
        with self.assertRaisesRegex(ValueError, "ENTRY_DOES_NOT_MATCH"):
            simulate_candidate(
                candidate(),
                bars((1, 100.2, 101.0, 99.0, 100.5)),
                cost_profile=costs(),
                tick_size=0.1,
                now=NOW,
            )

    def test_bars_must_be_strictly_chronological(self):
        duplicate = bars(
            (1, 100.0, 101.0, 99.0, 100.5),
            (1, 100.0, 101.0, 99.0, 100.5),
        )
        with self.assertRaisesRegex(ValueError, "NOT_STRICTLY_CHRONOLOGICAL"):
            simulate_candidate(
                candidate(), duplicate, cost_profile=costs(),
                tick_size=0.1, now=NOW,
            )


if __name__ == "__main__":
    unittest.main()
