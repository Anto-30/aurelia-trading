from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from research.labs.smc_reference_evaluator import evaluate_reference_outcome
from research.labs.smc_trend_agent import OHLCBar, SMCConfig, detect_smc_setup


def _stamp(start: datetime, index: int) -> str:
    return (start + timedelta(minutes=15 * index)).isoformat().replace("+00:00", "Z")


def _bar(start: datetime, index: int, values: tuple[float, float, float, float]) -> OHLCBar:
    return OHLCBar(_stamp(start, index), *values)


def _setup():
    start_15m = datetime(2025, 1, 1, 3, 15, tzinfo=timezone.utc)
    bars_15m = [
        _bar(start_15m, i, (100.0, 101.0, 99.0, 100.0)) for i in range(100)
    ]
    edits_15m = {
        60: (100.0, 102.0, 99.0, 101.5),
        65: (100.0, 101.0, 98.0, 99.0),
        70: (101.0, 104.0, 100.0, 103.0),
        75: (100.0, 101.0, 97.0, 98.0),
        80: (102.0, 106.0, 101.0, 105.0),
        85: (99.0, 101.0, 96.0, 100.0),
        97: (103.0, 105.0, 102.0, 104.0),
        98: (104.0, 105.0, 101.5, 103.0),
        99: (106.0, 110.0, 105.5, 110.0),
    }
    for i, values in edits_15m.items():
        bars_15m[i] = _bar(start_15m, i, values)

    start_1h = datetime(2025, 1, 1, 3, 0, tzinfo=timezone.utc)
    bars_1h = [
        OHLCBar(
            (start_1h + timedelta(hours=i)).isoformat().replace("+00:00", "Z"),
            100.0, 101.0, 99.0, 100.0,
        )
        for i in range(25)
    ]
    edits_1h = {
        5: (100.0, 102.0, 99.5, 101.5),
        8: (100.0, 101.0, 98.0, 99.0),
        10: (101.0, 104.0, 100.0, 103.0),
        13: (100.0, 101.0, 98.5, 99.0),
        15: (103.0, 106.0, 102.0, 105.0),
        18: (100.0, 101.0, 98.8, 99.5),
    }
    for i, (o, h, l, c) in edits_1h.items():
        stamp = (start_1h + timedelta(hours=i)).isoformat().replace("+00:00", "Z")
        bars_1h[i] = OHLCBar(stamp, o, h, l, c)
    config = SMCConfig(
        atr_period=5, displacement_atr_multiple=0.5,
        min_fvg_atr_multiple=0.1, tick_size=0.1, max_pending_bars=3,
    )
    setup = detect_smc_setup(
        bars_15m, bars_1h, symbol="TEST_SYNTHETIC", config=config
    )
    assert setup is not None
    return setup


def _after(setup, index: int, values: tuple[float, float, float, float]) -> OHLCBar:
    stamp = datetime.fromisoformat(setup.signal_timestamp_utc.replace("Z", "+00:00"))
    timestamp = (stamp + timedelta(minutes=15 * index)).isoformat().replace("+00:00", "Z")
    return OHLCBar(timestamp, *values)


class SMCReferenceOutcomeTests(unittest.TestCase):
    def test_target_after_entry_is_gross_reference_r_not_net_pnl(self):
        setup = _setup()
        entry = setup.entry_limit_reference
        first = _after(setup, 1, (110.0, 111.0, entry - 0.2, 108.0))
        second = _after(
            setup, 2,
            (entry + 1.0, setup.target_reference + 1.0, entry + 0.2,
             setup.target_reference + 0.5),
        )
        result = evaluate_reference_outcome(setup, [first, second])
        self.assertEqual(result.status, "TARGET_REFERENCE")
        self.assertAlmostEqual(result.gross_reference_r, setup.target_multiple_r)
        self.assertIsNone(result.net_reference_r)
        self.assertEqual(result.cost_status, "UNKNOWN")
        self.assertFalse(result.capital_authority)
        self.assertFalse(result.order_submission_permitted)

    def test_stop_after_reference_entry_is_minus_one_r(self):
        setup = _setup()
        entry = setup.entry_limit_reference
        first = _after(setup, 1, (110.0, 111.0, entry - 0.2, 108.0))
        second = _after(
            setup, 2,
            (entry, entry + 1.0, setup.stop_reference - 0.1,
             setup.order_block_low + 0.1),
        )
        result = evaluate_reference_outcome(setup, [first, second])
        self.assertEqual(result.status, "STOP_REFERENCE")
        self.assertEqual(result.gross_reference_r, -1.0)
        self.assertFalse(result.ambiguous_path)

    def test_target_and_entry_in_same_bar_is_not_counted_as_a_win(self):
        setup = _setup()
        entry = setup.entry_limit_reference
        bar = _after(
            setup, 1,
            (entry + 0.5, setup.target_reference + 1.0,
             entry - 0.1, entry + 0.2),
        )
        result = evaluate_reference_outcome(setup, [bar])
        self.assertEqual(result.status, "AMBIGUOUS_ENTRY_BAR")
        self.assertTrue(result.ambiguous_path)
        self.assertIsNone(result.gross_reference_r)

    def test_same_bar_stop_and_target_uses_conservative_stop_first(self):
        setup = _setup()
        entry = setup.entry_limit_reference
        entry_bar = _after(setup, 1, (110.0, 111.0, entry - 0.2, 108.0))
        exit_bar = _after(
            setup, 2,
            (entry, setup.target_reference + 1.0,
             setup.stop_reference - 0.1, entry),
        )
        result = evaluate_reference_outcome(setup, [entry_bar, exit_bar])
        self.assertEqual(result.status, "STOP_REFERENCE")
        self.assertEqual(result.gross_reference_r, -1.0)
        self.assertTrue(result.ambiguous_path)
        self.assertEqual(result.resolution_rule, "STOP_FIRST_CONSERVATIVE_SAME_BAR_EXIT")

    def test_pending_entry_expires_without_touch(self):
        setup = _setup()
        bars = [
            _after(setup, i, (102.0, 102.5, 101.8, 102.0))
            for i in range(1, setup.expires_after_bars + 1)
        ]
        result = evaluate_reference_outcome(setup, bars)
        self.assertEqual(result.status, "ENTRY_NOT_TOUCHED")
        self.assertEqual(result.elapsed_bars, setup.expires_after_bars)
        self.assertFalse(result.entry_reference_touched)

    def test_invalidation_before_entry_has_no_r_outcome(self):
        setup = _setup()
        bar = _after(
            setup, 1,
            (102.0, 102.5, setup.order_block_low - 1.0,
             setup.order_block_low - 0.1),
        )
        result = evaluate_reference_outcome(setup, [bar])
        self.assertEqual(result.status, "INVALIDATED_BEFORE_ENTRY")
        self.assertIsNone(result.gross_reference_r)

    def test_bar_at_or_before_signal_is_rejected(self):
        setup = _setup()
        signal = datetime.fromisoformat(setup.signal_timestamp_utc.replace("Z", "+00:00"))
        bar = OHLCBar(signal.isoformat().replace("+00:00", "Z"), 102.0, 102.5, 101.8, 102.0)
        with self.assertRaisesRegex(ValueError, "FOLLOW_UP_BAR_NOT_AFTER_SIGNAL"):
            evaluate_reference_outcome(setup, [bar])


if __name__ == "__main__":
    unittest.main()
