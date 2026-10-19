from __future__ import annotations

import unittest
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from research.labs.session_breakout_candidates import OHLCBar
from research.labs.session_structure_hypotheses import (
    SessionKey,
    SessionSummary,
    build_session_summaries,
    classify_new_york_session,
    confirmed_pivots,
    detect_session_reversal,
    directional_alignment,
    session_expansion_observation,
    multi_timeframe_context,
    structure_asof,
)

NY = ZoneInfo("America/New_York")
DAY = date(2026, 10, 8)


def make_session_bars(
    session_date: date,
    name: str = "EUROPE",
    *,
    sweep_first_bar: str | None = None,
) -> list[OHLCBar]:
    if name == "OVERNIGHT":
        start = datetime.combine(session_date - timedelta(days=1), time(18, 0), NY)
        end = datetime.combine(session_date, time(2, 0), NY)
    elif name == "EUROPE":
        start = datetime.combine(session_date, time(2, 0), NY)
        end = datetime.combine(session_date, time(9, 30), NY)
    else:
        start = datetime.combine(session_date, time(9, 30), NY)
        end = datetime.combine(session_date, time(17, 0), NY)

    bars: list[OHLCBar] = []
    stamp = start
    index = 0
    while stamp < end:
        o, h, l, c = 100.0, 101.0, 99.0, 100.0
        if index == 0 and sweep_first_bar == "LONG":
            o, h, l, c = 96.0, 98.0, 94.75, 96.0
        elif index == 0 and sweep_first_bar == "SHORT":
            o, h, l, c = 104.0, 105.25, 102.0, 104.0
        elif index == 0 and sweep_first_bar == "BOTH":
            o, h, l, c = 100.0, 105.25, 94.75, 100.0
        bars.append(OHLCBar(stamp.astimezone(timezone.utc), o, h, l, c))
        stamp += timedelta(minutes=5)
        index += 1
    return bars


def structure_bars() -> list[OHLCBar]:
    highs = [102.0, 103.0, 110.0, 104.0, 103.0, 112.0, 109.0, 107.0, 106.0]
    lows = [98.0, 97.0, 99.0, 95.0, 97.5, 98.0, 96.0, 97.0, 98.0]
    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    bars = []
    for i, (high, low) in enumerate(zip(highs, lows)):
        bars.append(OHLCBar(
            timestamp_utc=start + timedelta(hours=i),
            open=100.0,
            high=high,
            low=low,
            close=100.0,
        ))
    return bars


class SessionStructureHypothesisTests(unittest.TestCase):
    def test_classify_session_windows_and_exclude_maintenance(self):
        self.assertEqual(
            classify_new_york_session(datetime(2026, 10, 7, 22, 0, tzinfo=NY)),
            SessionKey(date(2026, 10, 8), "OVERNIGHT"),
        )
        self.assertEqual(
            classify_new_york_session(datetime(2026, 10, 8, 1, 55, tzinfo=NY)),
            SessionKey(date(2026, 10, 8), "OVERNIGHT"),
        )
        self.assertEqual(
            classify_new_york_session(datetime(2026, 10, 8, 2, 0, tzinfo=NY)),
            SessionKey(date(2026, 10, 8), "EUROPE"),
        )
        self.assertEqual(
            classify_new_york_session(datetime(2026, 10, 8, 9, 30, tzinfo=NY)),
            SessionKey(date(2026, 10, 8), "US_DAY"),
        )
        self.assertIsNone(classify_new_york_session(datetime(2026, 10, 8, 17, 30, tzinfo=NY)))

    def test_session_summary_requires_complete_grid(self):
        bars = make_session_bars(DAY, "EUROPE")
        summaries = build_session_summaries(bars)
        summary = next(s for s in summaries if s.key == SessionKey(DAY, "EUROPE"))
        self.assertEqual(summary.bar_count, 90)
        self.assertTrue(summary.complete_grid)
        missing = bars[:-1]
        incomplete = build_session_summaries(missing)
        item = next(s for s in incomplete if s.key == SessionKey(DAY, "EUROPE"))
        self.assertFalse(item.complete_grid)

    def test_session_reversal_detects_first_long_reentry_after_low_sweep(self):
        key = SessionKey(DAY, "EUROPE")
        previous = SessionSummary(
            key=SessionKey(DAY - timedelta(days=1), "US_DAY"),
            start_utc=datetime(2026, 10, 7, 13, 30, tzinfo=timezone.utc),
            end_utc=datetime(2026, 10, 7, 21, 0, tzinfo=timezone.utc),
            high=105.0, low=95.0, bar_count=90, complete_grid=True,
        )
        bars = make_session_bars(DAY, "EUROPE", sweep_first_bar="LONG")
        signal = detect_session_reversal(bars, key, previous, tick_size=0.25)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.direction, "LONG")
        self.assertEqual(signal.signal_bar_open_utc, bars[0].timestamp_utc)
        self.assertEqual(signal.signal_available_at_utc, bars[0].timestamp_utc + timedelta(minutes=5))
        self.assertAlmostEqual(signal.stop_reference_price, 94.5)
        self.assertFalse(signal.capital_authority)
        self.assertFalse(signal.live_execution)

    def test_session_reversal_short_signal(self):
        key = SessionKey(DAY, "EUROPE")
        previous = SessionSummary(
            key=SessionKey(DAY - timedelta(days=1), "US_DAY"),
            start_utc=datetime(2026, 10, 7, 13, 30, tzinfo=timezone.utc),
            end_utc=datetime(2026, 10, 7, 21, 0, tzinfo=timezone.utc),
            high=105.0, low=95.0, bar_count=90, complete_grid=True,
        )
        bars = make_session_bars(DAY, "EUROPE", sweep_first_bar="SHORT")
        signal = detect_session_reversal(bars, key, previous, tick_size=0.25)
        self.assertEqual(signal.direction, "SHORT")
        self.assertAlmostEqual(signal.stop_reference_price, 105.5)

    def test_both_boundaries_swept_in_one_bar_is_ambiguous_without_direction(self):
        key = SessionKey(DAY, "EUROPE")
        previous = SessionSummary(
            key=SessionKey(DAY - timedelta(days=1), "US_DAY"),
            start_utc=datetime(2026, 10, 7, 13, 30, tzinfo=timezone.utc),
            end_utc=datetime(2026, 10, 7, 21, 0, tzinfo=timezone.utc),
            high=105.0, low=95.0, bar_count=90, complete_grid=True,
        )
        bars = make_session_bars(DAY, "EUROPE", sweep_first_bar="BOTH")
        signal = detect_session_reversal(bars, key, previous, tick_size=0.25)
        self.assertTrue(signal.ambiguity)
        self.assertIsNone(signal.direction)

    def test_gapped_session_is_rejected_for_reversal(self):
        key = SessionKey(DAY, "EUROPE")
        previous = SessionSummary(
            key=SessionKey(DAY - timedelta(days=1), "US_DAY"),
            start_utc=datetime(2026, 10, 7, 13, 30, tzinfo=timezone.utc),
            end_utc=datetime(2026, 10, 7, 21, 0, tzinfo=timezone.utc),
            high=105.0, low=95.0, bar_count=90, complete_grid=True,
        )
        bars = make_session_bars(DAY, "EUROPE", sweep_first_bar="LONG")
        with self.assertRaisesRegex(ValueError, "SESSION_WINDOW_INCOMPLETE_OR_GAPPED"):
            detect_session_reversal(bars[:-1], key, previous, tick_size=0.25)

    def test_following_session_expansion_is_descriptive_not_authoritative(self):
        from research.labs.session_structure_hypotheses import SessionReversalSignal
        key = SessionKey(DAY, "EUROPE")
        next_key = SessionKey(DAY, "US_DAY")
        signal = SessionReversalSignal(
            key=key,
            direction="LONG",
            signal_bar_open_utc=datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc),
            signal_available_at_utc=datetime(2026, 10, 8, 6, 5, tzinfo=timezone.utc),
            signal_price=96.0,
            prior_session_high=105.0,
            prior_session_low=95.0,
            stop_reference_price=94.5,
        )
        following = SessionSummary(
            key=next_key,
            start_utc=datetime(2026, 10, 8, 13, 30, tzinfo=timezone.utc),
            end_utc=datetime(2026, 10, 8, 21, 0, tzinfo=timezone.utc),
            high=112.0, low=88.0, bar_count=90, complete_grid=True,
        )
        obs = session_expansion_observation(signal, following, [4.0, 5.0, 6.0])
        self.assertEqual(obs.prior_20_same_type_median_range, 5.0)
        self.assertAlmostEqual(obs.following_session_range, 24.0)
        self.assertAlmostEqual(obs.expansion_ratio, 4.8)
        self.assertFalse(obs.capital_authority)

    def test_zero_or_missing_prior_median_keeps_expansion_ratio_unknown(self):
        from research.labs.session_structure_hypotheses import SessionReversalSignal
        key = SessionKey(DAY, "EUROPE")
        signal = SessionReversalSignal(
            key=key, direction="LONG",
            signal_bar_open_utc=datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc),
            signal_available_at_utc=datetime(2026, 10, 8, 6, 5, tzinfo=timezone.utc),
            signal_price=96.0, prior_session_high=105.0, prior_session_low=95.0,
            stop_reference_price=94.5,
        )
        following = SessionSummary(
            key=SessionKey(DAY, "US_DAY"),
            start_utc=datetime(2026, 10, 8, 13, 30, tzinfo=timezone.utc),
            end_utc=datetime(2026, 10, 8, 21, 0, tzinfo=timezone.utc),
            high=105.0, low=95.0, bar_count=90, complete_grid=True,
        )
        self.assertIsNone(session_expansion_observation(signal, following, []).expansion_ratio)
        self.assertIsNone(session_expansion_observation(signal, following, [0.0, 0.0]).expansion_ratio)

    def test_session_summary_rejects_unimplemented_interval(self):
        with self.assertRaisesRegex(ValueError, "SESSION_SUMMARY_REQUIRES_5M_BARS"):
            build_session_summaries(
                make_session_bars(DAY, "EUROPE"),
                expected_interval=timedelta(minutes=1),
            )

    def test_structure_rejects_nonpositive_pivot_history_limit(self):
        with self.assertRaisesRegex(ValueError, "MAX_PIVOTS_MUST_BE_POSITIVE"):
            structure_asof(
                structure_bars(),
                timeframe=timedelta(hours=1),
                timeframe_label="1H",
                decision_timestamp=datetime(2026, 1, 6, 0, 0, tzinfo=timezone.utc),
                max_pivots=0,
            )

    def test_confirmed_pivot_is_unavailable_before_two_right_bars_close(self):
        bars = structure_bars()
        pivots = confirmed_pivots(bars, timeframe=timedelta(hours=1))
        pivot = next(p for p in pivots if p.kind == "HIGH" and p.price == 110.0)
        self.assertEqual(pivot.pivot_bar_open_utc, bars[2].timestamp_utc)
        self.assertEqual(pivot.confirmation_available_at_utc, bars[4].timestamp_utc + timedelta(hours=1))
        early = structure_asof(
            bars, timeframe=timedelta(hours=1), timeframe_label="1H",
            decision_timestamp=pivot.confirmation_available_at_utc - timedelta(microseconds=1),
        )
        self.assertNotIn(pivot, early.confirmed_highs)
        on_time = structure_asof(
            bars, timeframe=timedelta(hours=1), timeframe_label="1H",
            decision_timestamp=pivot.confirmation_available_at_utc,
        )
        self.assertIn(pivot, on_time.confirmed_highs)

    def test_structure_bullish_only_after_both_confirmed_swing_pairs(self):
        bars = structure_bars()
        decision = bars[-1].timestamp_utc + timedelta(hours=1)
        state = structure_asof(
            bars, timeframe=timedelta(hours=1), timeframe_label="1H",
            decision_timestamp=decision,
        )
        self.assertEqual(state.bias, "BULLISH")
        self.assertGreaterEqual(len(state.confirmed_highs), 2)
        self.assertGreaterEqual(len(state.confirmed_lows), 2)

    def test_multi_timeframe_missing_input_is_unknown_not_pass(self):
        bars = structure_bars()
        states = multi_timeframe_context(
            {"1H": bars},
            {"1H": timedelta(hours=1), "4H": timedelta(hours=4)},
            decision_timestamp=bars[-1].timestamp_utc + timedelta(hours=1),
        )
        self.assertEqual(states["4H"].bias, "UNKNOWN")
        self.assertEqual(directional_alignment(states, "LONG"), "UNKNOWN")

    def test_directional_alignment_requires_every_requested_timeframe(self):
        from research.labs.session_structure_hypotheses import StructureState
        asof = datetime(2026, 1, 1, tzinfo=timezone.utc)
        good = StructureState("1H", asof, "BULLISH", (), (), 4)
        bad = StructureState("4H", asof, "BEARISH", (), (), 6)
        self.assertEqual(directional_alignment({"1H": good}, "LONG"), "PASS")
        self.assertEqual(directional_alignment({"1H": good, "4H": bad}, "LONG"), "FAIL")


if __name__ == "__main__":
    unittest.main()
