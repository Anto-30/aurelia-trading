from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from research.labs.smc_trend_agent import (
    OHLCBar,
    SMCConfig,
    assess_pending_setup,
    confirmed_swings,
    detect_smc_setup,
    latest_fvg,
    structure_bias,
    wilder_atr,
)


def _stamp(start: datetime, index: int, seconds: int) -> str:
    return (start + timedelta(seconds=index * seconds)).isoformat().replace("+00:00", "Z")


def _bar(start: datetime, index: int, seconds: int, values: tuple[float, float, float, float]) -> OHLCBar:
    open_price, high, low, close = values
    return OHLCBar(_stamp(start, index, seconds), open_price, high, low, close)


def _fixture_15m() -> list[OHLCBar]:
    start = datetime(2025, 1, 1, 3, 15, tzinfo=timezone.utc)
    bars = [_bar(start, i, 900, (100.0, 101.0, 99.0, 100.0)) for i in range(100)]
    edits = {
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
    for index, values in edits.items():
        bars[index] = _bar(start, index, 900, values)
    return bars


def _fixture_1h() -> list[OHLCBar]:
    start = datetime(2025, 1, 1, 3, 0, tzinfo=timezone.utc)
    bars = [_bar(start, i, 3600, (100.0, 101.0, 99.0, 100.0)) for i in range(25)]
    edits = {
        5: (100.0, 102.0, 99.5, 101.5),
        8: (100.0, 101.0, 98.0, 99.0),
        10: (101.0, 104.0, 100.0, 103.0),
        13: (100.0, 101.0, 98.5, 99.0),
        15: (103.0, 106.0, 102.0, 105.0),
        18: (100.0, 101.0, 98.8, 99.5),
    }
    for index, values in edits.items():
        bars[index] = _bar(start, index, 3600, values)
    return bars


class SMCTrendAgentTests(unittest.TestCase):
    def test_invalid_ohlc_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "BAR_HIGH_INCONSISTENT"):
            OHLCBar("2025-01-01T00:00:00Z", 10.0, 9.0, 8.0, 9.5)

    def test_naive_timestamp_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "BAR_TIMESTAMP_MUST_BE_TIMEZONE_AWARE"):
            OHLCBar("2025-01-01T00:00:00", 10.0, 11.0, 9.0, 10.5)

    def test_wilder_atr_has_a_warmup_period(self) -> None:
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        bars = [_bar(start, i, 900, (10.0, 11.0, 9.0, 10.0)) for i in range(5)]
        values = wilder_atr(bars, period=3)
        self.assertEqual(values[:2], [None, None])
        self.assertAlmostEqual(values[2], 2.0)
        self.assertAlmostEqual(values[4], 2.0)

    def test_latest_fvg_requires_gap_wider_than_threshold(self) -> None:
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        bars = [
            _bar(start, 0, 900, (10.0, 10.5, 9.5, 10.2)),
            _bar(start, 1, 900, (10.2, 11.0, 10.0, 10.7)),
            _bar(start, 2, 900, (11.0, 12.0, 11.0, 11.8)),
        ]
        fvg = latest_fvg(bars, direction="LONG", atr=1.0, min_atr_multiple=0.4)
        self.assertIsNotNone(fvg)
        assert fvg is not None
        self.assertAlmostEqual(fvg.lower_price, 10.5)
        self.assertAlmostEqual(fvg.upper_price, 11.0)
        self.assertIsNone(latest_fvg(bars, direction="LONG", atr=1.0, min_atr_multiple=0.5))

    def test_unconfirmed_last_bar_is_not_reported_as_a_swing(self) -> None:
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        values = [
            (10.0, 11.0, 9.0, 10.0),
            (10.0, 12.0, 9.5, 11.0),
            (11.0, 15.0, 10.0, 14.0),
        ]
        bars = [_bar(start, i, 900, row) for i, row in enumerate(values)]
        swings = confirmed_swings(bars, left_bars=1, right_bars=1)
        self.assertFalse(any(point.index == len(bars) - 1 for point in swings))

    def test_higher_timeframe_aligned_setup_is_research_only(self) -> None:
        config = SMCConfig(
            atr_period=5,
            displacement_atr_multiple=0.5,
            min_fvg_atr_multiple=0.1,
            order_block_lookback_bars=8,
            tick_size=0.1,
            target_multiple_r=2.0,
        )
        setup = detect_smc_setup(
            _fixture_15m(), _fixture_1h(), symbol="TEST_SYNTHETIC", config=config
        )
        self.assertIsNotNone(setup)
        assert setup is not None
        self.assertEqual(setup.direction, "LONG")
        self.assertEqual(setup.structure_event, "BOS")
        self.assertEqual(setup.higher_timeframe_bias, "BULLISH")
        self.assertLess(setup.entry_limit_reference, setup.signal_close)
        self.assertGreater(setup.target_reference, setup.signal_close)
        self.assertAlmostEqual(
            setup.target_reference - setup.entry_limit_reference,
            setup.risk_distance * setup.target_multiple_r,
        )
        self.assertTrue(setup.research_only)
        self.assertFalse(setup.capital_authority)
        self.assertFalse(setup.order_submission_permitted)

    def test_neutral_or_unavailable_higher_timeframe_blocks_setup(self) -> None:
        config = SMCConfig(
            atr_period=5,
            displacement_atr_multiple=0.5,
            min_fvg_atr_multiple=0.1,
            tick_size=0.1,
            require_higher_timeframe_alignment=True,
        )
        self.assertIsNone(detect_smc_setup(
            _fixture_15m(), [], symbol="TEST_SYNTHETIC", config=config
        ))

    def test_pending_setup_invalidation_precedes_level_touch(self) -> None:
        config = SMCConfig(
            atr_period=5,
            displacement_atr_multiple=0.5,
            min_fvg_atr_multiple=0.1,
            tick_size=0.1,
        )
        setup = detect_smc_setup(
            _fixture_15m(), _fixture_1h(), symbol="TEST_SYNTHETIC", config=config
        )
        self.assertIsNotNone(setup)
        assert setup is not None
        start = datetime.fromisoformat(setup.signal_timestamp_utc.replace("Z", "+00:00"))
        after = _bar(start, 1, 900, (102.0, 106.0, 100.0, 101.0))
        status = assess_pending_setup(setup, [after])
        self.assertEqual(status.status, "INVALIDATED")
        self.assertEqual(status.reason, "CLOSE_BEYOND_ORDER_BLOCK")

    def test_touch_is_not_misreported_as_a_broker_fill(self) -> None:
        config = SMCConfig(
            atr_period=5,
            displacement_atr_multiple=0.5,
            min_fvg_atr_multiple=0.1,
            tick_size=0.1,
        )
        setup = detect_smc_setup(
            _fixture_15m(), _fixture_1h(), symbol="TEST_SYNTHETIC", config=config
        )
        self.assertIsNotNone(setup)
        assert setup is not None
        start = datetime.fromisoformat(setup.signal_timestamp_utc.replace("Z", "+00:00"))
        low = setup.entry_limit_reference - 0.05
        high = setup.entry_limit_reference + 0.05
        after = _bar(start, 1, 900, (setup.entry_limit_reference, high, low, setup.entry_limit_reference))
        status = assess_pending_setup(setup, [after])
        self.assertEqual(status.status, "ENTRY_LEVEL_TOUCHED")
        self.assertEqual(status.reason, "PRICE_INTERSECTED_REFERENCE_LEVEL_ONLY")


    def test_future_higher_timeframe_bar_cannot_change_existing_candidate(self) -> None:
        config = SMCConfig(
            atr_period=5,
            displacement_atr_multiple=0.5,
            min_fvg_atr_multiple=0.1,
            order_block_lookback_bars=8,
            tick_size=0.1,
        )
        baseline = detect_smc_setup(
            _fixture_15m(), _fixture_1h(), symbol="TEST_SYNTHETIC", config=config
        )
        self.assertIsNotNone(baseline)
        start = datetime(2025, 1, 1, 3, 0, tzinfo=timezone.utc)
        # This hostile bar closes after the signal timestamp; it must not leak
        # into the 1h bias used for this already-closed 15m signal.
        future = _bar(start, 26, 3600, (100.0, 140.0, 60.0, 65.0))
        with_future = detect_smc_setup(
            _fixture_15m(), [*_fixture_1h(), future],
            symbol="TEST_SYNTHETIC", config=config
        )
        self.assertEqual(with_future, baseline)

    def test_confirmed_swings_are_prefix_stable(self) -> None:
        bars = _fixture_15m()
        cut = 90
        earlier = confirmed_swings(bars[:cut], left_bars=2, right_bars=2)
        full = confirmed_swings(bars, left_bars=2, right_bars=2)
        # Pivots confirmed by the prefix end must not change when later data
        # arrives. Pivots that need right-side confirmation are not observable.
        prefix_observable = [p for p in earlier if p.confirmed_at_index < cut]
        full_observable = [p for p in full if p.confirmed_at_index < cut]
        self.assertEqual(prefix_observable, full_observable)

    def test_pending_setup_expires_at_configured_bar_count(self) -> None:
        config = SMCConfig(
            atr_period=5,
            displacement_atr_multiple=0.5,
            min_fvg_atr_multiple=0.1,
            tick_size=0.1,
            max_pending_bars=3,
        )
        setup = detect_smc_setup(
            _fixture_15m(), _fixture_1h(), symbol="TEST_SYNTHETIC", config=config
        )
        self.assertIsNotNone(setup)
        assert setup is not None
        start = datetime.fromisoformat(setup.signal_timestamp_utc.replace("Z", "+00:00"))
        safe_bars = [
            _bar(start, index, 900, (102.0, 102.5, 101.8, 102.0))
            for index in range(1, 4)
        ]
        status = assess_pending_setup(setup, safe_bars)
        self.assertEqual(status.status, "EXPIRED")
        self.assertEqual(status.bars_elapsed, 3)
        self.assertEqual(status.reason, "PENDING_SETUP_TIME_TO_LIVE_EXCEEDED")

    def test_follow_up_bar_at_or_before_signal_is_rejected(self) -> None:
        config = SMCConfig(
            atr_period=5,
            displacement_atr_multiple=0.5,
            min_fvg_atr_multiple=0.1,
            tick_size=0.1,
        )
        setup = detect_smc_setup(
            _fixture_15m(), _fixture_1h(), symbol="TEST_SYNTHETIC", config=config
        )
        self.assertIsNotNone(setup)
        assert setup is not None
        signal = datetime.fromisoformat(setup.signal_timestamp_utc.replace("Z", "+00:00"))
        not_after = _bar(signal, 0, 900, (102.0, 102.5, 101.8, 102.0))
        with self.assertRaisesRegex(ValueError, "FOLLOW_UP_BAR_NOT_AFTER_SIGNAL"):
            assess_pending_setup(setup, [not_after])


if __name__ == "__main__":
    unittest.main()
