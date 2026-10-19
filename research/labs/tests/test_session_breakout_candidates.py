from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from research.labs.session_breakout_candidates import (
    OHLCBar,
    QuoteTick,
    opening_range_30m_from_15m,
    opening_range_close_candidate,
    premarket_close_candidate,
    premarket_intrabar_candidate,
    premarket_range_5m,
)

NY = ZoneInfo("America/New_York")


def bar(day: date, local_time: time, values: tuple[float, float, float, float], minutes: int = 5) -> OHLCBar:
    stamp = datetime.combine(day, local_time, NY).astimezone(timezone.utc)
    return OHLCBar(stamp, *values)


def premarket_bars(day: date, overrides: dict[time, tuple[float, float, float, float]] | None = None) -> list[OHLCBar]:
    overrides = overrides or {}
    result = []
    stamp = datetime.combine(day, time(4, 0), NY)
    end = datetime.combine(day, time(11, 5), NY)
    while stamp < end:
        values = overrides.get(stamp.time(), (100.0, 101.0, 99.0, 100.0))
        result.append(OHLCBar(stamp.astimezone(timezone.utc), *values))
        stamp += timedelta(minutes=5)
    # Put the reference range high and low inside the eligible 04:00-09:00 window.
    for i, row in enumerate(result):
        local = row.timestamp_utc.astimezone(NY)
        if local.time() == time(4, 50):
            result[i] = OHLCBar(row.timestamp_utc, 100.0, 105.0, 99.0, 100.0)
        if local.time() == time(5, 40):
            result[i] = OHLCBar(row.timestamp_utc, 100.0, 101.0, 95.0, 100.0)
    return result


def opening_range_bars(day: date) -> list[OHLCBar]:
    return [
        bar(day, time(9, 30), (100.0, 104.0, 96.0, 101.0), 15),
        bar(day, time(9, 45), (101.0, 105.0, 95.0, 100.0), 15),
    ]


def five_minute_opening_window(day: date, breakout: time | None = time(10, 0)) -> list[OHLCBar]:
    result = []
    stamp = datetime.combine(day, time(9, 30), NY)
    end = datetime.combine(day, time(11, 0), NY)
    while stamp < end:
        if breakout is not None and stamp.time() == breakout:
            values = (100.0, 107.0, 99.0, 106.0)
        elif breakout is not None and stamp.time() == (datetime.combine(day, breakout) + timedelta(minutes=5)).time():
            values = (106.5, 107.0, 106.0, 106.6)
        else:
            values = (100.0, 104.0, 96.0, 100.0)
        result.append(OHLCBar(stamp.astimezone(timezone.utc), *values))
        stamp += timedelta(minutes=5)
    return result


class SessionBreakoutCandidateTests(unittest.TestCase):
    def test_premarket_range_uses_60_bars_and_exclusive_end(self):
        day = date(2026, 10, 8)
        result = premarket_range_5m(premarket_bars(day), day)
        self.assertEqual(result.bars_count, 60)
        self.assertEqual(result.high, 105.0)
        self.assertEqual(result.low, 95.0)
        self.assertEqual(result.end_utc.astimezone(NY).time(), time(9, 0))

    def test_timezone_conversion_handles_daylight_saving_time(self):
        spring_day = date(2026, 3, 9)
        fall_day = date(2026, 11, 2)
        spring = premarket_range_5m(premarket_bars(spring_day), spring_day)
        fall = premarket_range_5m(premarket_bars(fall_day), fall_day)
        self.assertEqual(spring.start_utc.hour, 8)
        self.assertEqual(fall.start_utc.hour, 9)

    def test_incomplete_range_is_rejected(self):
        day = date(2026, 10, 8)
        bars = premarket_bars(day)[:59]
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_SESSION_WINDOW"):
            premarket_range_5m(bars, day)

    def test_range_grid_gap_is_rejected(self):
        day = date(2026, 10, 8)
        bars = premarket_bars(day)
        index = next(i for i, x in enumerate(bars) if x.timestamp_utc.astimezone(NY).time() == time(4, 25))
        old = bars[index]
        bars[index] = OHLCBar(old.timestamp_utc + timedelta(minutes=1), old.open, old.high, old.low, old.close)
        bars.sort(key=lambda x: x.timestamp_utc)
        with self.assertRaisesRegex(ValueError, "BAR_NOT_ALIGNED|SESSION_WINDOW_GAP"):
            premarket_range_5m(bars, day)

    def test_completed_close_enters_at_next_bar_reference_and_sets_two_r_target(self):
        day = date(2026, 10, 8)
        bars = premarket_bars(day, {
            time(9, 30): (100.0, 107.0, 99.0, 106.0),
            time(9, 35): (106.5, 107.0, 106.0, 106.6),
        })
        price_range = premarket_range_5m(bars, day)
        result = premarket_close_candidate(
            bars, price_range, day, stop_mode="OPPOSITE_RANGE_BOUNDARY"
        )
        self.assertEqual(result.status, "CANDIDATE")
        self.assertEqual(result.candidate.direction, "LONG")
        self.assertEqual(result.candidate.entry_reference_price, 106.5)
        self.assertEqual(result.candidate.stop_price, 95.0)
        self.assertAlmostEqual(result.candidate.target_price, 129.5)
        self.assertFalse(result.candidate.capital_authority)
        self.assertFalse(result.candidate.live_execution)

    def test_completed_close_breakout_candle_stop_is_separate_variant(self):
        day = date(2026, 10, 8)
        bars = premarket_bars(day, {
            time(9, 30): (100.0, 107.0, 99.0, 106.0),
            time(9, 35): (106.5, 107.0, 106.0, 106.6),
        })
        price_range = premarket_range_5m(bars, day)
        result = premarket_close_candidate(
            bars, price_range, day, stop_mode="BREAKOUT_CANDLE_EXTREME", target_value=2.0
        )
        self.assertEqual(result.status, "CANDIDATE")
        self.assertAlmostEqual(result.candidate.stop_price, 98.75)
        self.assertAlmostEqual(result.candidate.target_price, 122.0)

    def test_no_breakout_returns_no_trade(self):
        day = date(2026, 10, 8)
        bars = premarket_bars(day)
        price_range = premarket_range_5m(bars, day)
        result = premarket_close_candidate(
            bars, price_range, day, stop_mode="OPPOSITE_RANGE_BOUNDARY"
        )
        self.assertEqual((result.status, result.reason), ("NO_TRADE", "NO_BREAKOUT"))

    def test_entry_signal_at_cutoff_is_rejected(self):
        day = date(2026, 10, 8)
        bars = premarket_bars(day, {
            time(10, 55): (100.0, 107.0, 99.0, 106.0),
        })
        price_range = premarket_range_5m(bars, day)
        result = premarket_close_candidate(
            bars, price_range, day, stop_mode="OPPOSITE_RANGE_BOUNDARY"
        )
        self.assertEqual(result.status, "NO_TRADE")

    def test_nonchronological_bars_are_rejected(self):
        day = date(2026, 10, 8)
        bars = premarket_bars(day)
        bars[10], bars[11] = bars[11], bars[10]
        with self.assertRaisesRegex(ValueError, "BARS_NOT_STRICTLY_CHRONOLOGICAL"):
            premarket_range_5m(bars, day)

    def test_opening_range_uses_exactly_two_completed_15m_bars(self):
        day = date(2026, 10, 8)
        result = opening_range_30m_from_15m(opening_range_bars(day), day)
        self.assertEqual(result.bars_count, 2)
        self.assertEqual((result.high, result.low), (105.0, 95.0))
        self.assertEqual(result.end_utc.astimezone(NY).time(), time(10, 0))

    def test_opening_range_target_variants_are_not_blended(self):
        day = date(2026, 10, 8)
        price_range = opening_range_30m_from_15m(opening_range_bars(day), day)
        bars = five_minute_opening_window(day)
        fixed = opening_range_close_candidate(
            bars, price_range, day, target_mode="FIXED_POINTS", target_value=10.0
        )
        fixed_r = opening_range_close_candidate(
            bars, price_range, day, target_mode="R_MULTIPLE", target_value=2.0
        )
        self.assertEqual(fixed.candidate.stop_price, 95.0)
        self.assertAlmostEqual(fixed.candidate.target_price, 116.5)
        self.assertAlmostEqual(fixed_r.candidate.target_price, 129.5)

    def test_intrabar_requires_a_later_executable_quote(self):
        day = date(2026, 10, 8)
        price_range = premarket_range_5m(premarket_bars(day), day)
        def tick(second: int, price: float, bid: float, ask: float, sequence: int) -> QuoteTick:
            local = datetime.combine(day, time(9, 30), NY) + timedelta(seconds=second)
            return QuoteTick(local.astimezone(timezone.utc), price, bid, ask, sequence)
        ticks = [
            tick(0, 104.0, 103.9, 104.1, 0),
            tick(1, 105.1, 105.0, 105.2, 1),
            tick(2, 105.4, 105.3, 105.5, 2),
        ]
        result = premarket_intrabar_candidate(
            ticks, price_range, day, stop_mode="OPPOSITE_RANGE_BOUNDARY"
        )
        self.assertEqual(result.status, "CANDIDATE")
        self.assertEqual(result.candidate.signal_timestamp_utc, ticks[1].timestamp_utc)
        self.assertEqual(result.candidate.entry_timestamp_utc, ticks[2].timestamp_utc)
        self.assertEqual(result.candidate.entry_reference_price, 105.5)
        self.assertEqual(result.candidate.price_reference, "NEXT_TICK_ASK_FOR_LONG_BID_FOR_SHORT")

    def test_intrabar_final_breakout_candle_stop_is_rejected_as_lookahead(self):
        day = date(2026, 10, 8)
        price_range = premarket_range_5m(premarket_bars(day), day)
        with self.assertRaisesRegex(ValueError, "WOULD_LOOK_AHEAD"):
            premarket_intrabar_candidate(
                [], price_range, day, stop_mode="BREAKOUT_CANDLE_EXTREME"
            )

    def test_intrabar_observed_extreme_stop_uses_only_prices_seen_at_signal(self):
        day = date(2026, 10, 8)
        price_range = premarket_range_5m(premarket_bars(day), day)
        def tick(second: int, price: float, bid: float, ask: float, sequence: int) -> QuoteTick:
            local = datetime.combine(day, time(9, 30), NY) + timedelta(seconds=second)
            return QuoteTick(local.astimezone(timezone.utc), price, bid, ask, sequence)
        ticks = [
            tick(0, 104.0, 103.9, 104.1, 0),
            tick(1, 105.1, 105.0, 105.2, 1),
            tick(2, 105.4, 105.3, 105.5, 2),
        ]
        result = premarket_intrabar_candidate(
            ticks, price_range, day, stop_mode="OBSERVED_EXTREME_AT_SIGNAL"
        )
        self.assertAlmostEqual(result.candidate.stop_price, 103.75)

    def test_candidate_module_is_research_only(self):
        from research.labs import session_breakout_candidates as module
        self.assertTrue(module.RESEARCH_ONLY)
        self.assertFalse(module.CAPITAL_AUTHORITY)
        self.assertFalse(module.LIVE_EXECUTION)


if __name__ == "__main__":
    unittest.main()
