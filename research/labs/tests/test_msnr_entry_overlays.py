from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from research.labs.deterministic_intraday_strategies import StrategyBar, StrategyCandidate
from research.labs.msnr_entry_overlays import (
    EntryOverlayConfig, build_msnr_entry_overlays,
)


def bar(i, o, h, l, c):
    stamp = (datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(minutes=i)).isoformat()
    return StrategyBar(stamp, o, h, l, c)


def signal(stamp, direction="LONG"):
    return StrategyCandidate(
        "MSNR_LIQUIDITY_SWEEP", "msnr-v1", direction, stamp,
        "NEXT_BAR_OPEN_AFTER_SIGNAL", 90.0, 110.0, "OPPOSING_REFERENCE_RANGE_EDGE",
        "RANGING_LOW_VOL", ("LIQUIDITY_LOW_SWEPT", "RANGE_RECLAIMED", "STRUCTURE_BREAK_CONFIRMED"),
    )


class MSNREntryOverlayTests(unittest.TestCase):
    def _fixture(self):
        # 15 quiet bars establish ATR; canonical MSNR signal is at index 14.
        rows = [bar(i, 100.0, 100.2, 99.8, 100.0) for i in range(15)]
        # V1 displacement at 15; bullish FVG between bar 13 high (100.2)
        # and bar 15 low (101.0). Retrace touches the upper FVG boundary.
        rows.append(bar(15, 101.2, 102.0, 101.0, 101.8))
        rows.append(bar(16, 101.5, 101.7, 100.8, 101.0))
        rows.append(bar(17, 101.2, 101.4, 100.9, 101.1))
        rows.append(bar(18, 101.1, 101.3, 100.8, 101.0))
        return rows

    def test_emits_three_distinct_non_executable_overlays(self):
        rows = self._fixture()
        candidate = signal(rows[14].timestamp_utc)
        events = build_msnr_entry_overlays(
            rows, [candidate],
            config=EntryOverlayConfig(atr_period=5, displacement_body_atr=1.0,
                                      max_bars_after_signal=5, max_retrace_bars_after_displacement=3),
        )
        by_variant = {event.variant: event for event in events}
        self.assertEqual(set(by_variant), {"V0_BASELINE", "V1_DISPLACEMENT_CLOSE", "V2_FVG_RETRACE"})
        self.assertEqual(by_variant["V0_BASELINE"].entry_price_proxy, rows[15].open)
        self.assertEqual(by_variant["V1_DISPLACEMENT_CLOSE"].entry_price_proxy, rows[15].close)
        self.assertEqual(by_variant["V2_FVG_RETRACE"].status, "FILLED_PROXY")
        self.assertAlmostEqual(by_variant["V2_FVG_RETRACE"].entry_price_proxy, 101.0)
        for event in events:
            payload = event.as_payload()
            self.assertTrue(payload["research_only"])
            self.assertFalse(payload["capital_authority"])
            self.assertFalse(payload["order_submission_permitted"])
            self.assertFalse(payload["price_is_executable"])

    def test_future_bars_cannot_change_already_emitted_overlay_events(self):
        rows = self._fixture()
        candidate = signal(rows[14].timestamp_utc)
        cfg = EntryOverlayConfig(atr_period=5, displacement_body_atr=1.0,
                                 max_bars_after_signal=5, max_retrace_bars_after_displacement=3)
        prefix_events = build_msnr_entry_overlays(rows[:19], [candidate], config=cfg)
        rows.append(bar(19, 101.2, 101.4, 100.9, 101.1))
        full_events = build_msnr_entry_overlays(rows, [candidate], config=cfg)
        # Every event emitted by the shorter prefix remains byte-for-byte equal
        # in the full history. Appending future bars cannot revise past entries.
        self.assertEqual(prefix_events, full_events)

    def test_signal_timestamp_must_exist_in_supplied_prefix(self):
        rows = self._fixture()
        candidate = signal("2026-11-02T00:00:00+00:00")
        with self.assertRaisesRegex(ValueError, "OVERLAY_SIGNAL_TIMESTAMP_NOT_IN_BAR_PREFIX"):
            build_msnr_entry_overlays(rows, [candidate])

    def test_rejects_non_msnr_and_executable_candidates(self):
        rows = self._fixture()
        candidate = signal(rows[14].timestamp_utc)
        bad = StrategyCandidate(
            "OPENING_RANGE_BREAKOUT", candidate.version, candidate.direction,
            candidate.signal_timestamp_utc, candidate.entry_timing,
            candidate.stop_reference_price, candidate.target_reference_price,
            candidate.target_mode, candidate.regime, candidate.evidence_codes,
        )
        with self.assertRaisesRegex(ValueError, "OVERLAY_ACCEPTS_CANONICAL_MSNR_SIGNALS_ONLY"):
            build_msnr_entry_overlays(rows, [bad])

    def test_missing_retrace_is_explicit_not_silently_dropped(self):
        rows = [bar(i, 100, 100.2, 99.8, 100) for i in range(15)]
        rows.append(bar(15, 101.2, 102, 101, 101.8))
        rows.append(bar(16, 102.0, 102.2, 101.5, 101.8))
        rows.append(bar(17, 101.8, 102.1, 101.4, 101.7))
        candidate = signal(rows[14].timestamp_utc)
        events = build_msnr_entry_overlays(
            rows, [candidate],
            config=EntryOverlayConfig(atr_period=5, displacement_body_atr=1.0,
                                      max_bars_after_signal=5, max_retrace_bars_after_displacement=2),
        )
        v2 = next(e for e in events if e.variant == "V2_FVG_RETRACE")
        self.assertEqual(v2.status, "PENDING_RETRACE_WINDOW")
        self.assertIsNone(v2.entry_price_proxy)

    def test_completed_retrace_window_records_a_miss(self):
        rows = [bar(i, 100, 100.2, 99.8, 100) for i in range(15)]
        rows.append(bar(15, 101.2, 102, 101, 101.8))
        rows.append(bar(16, 101.5, 102, 101.1, 101.6))
        rows.append(bar(17, 101.6, 102.1, 101.2, 101.7))
        candidate = signal(rows[14].timestamp_utc)
        events = build_msnr_entry_overlays(
            rows, [candidate],
            config=EntryOverlayConfig(atr_period=5, displacement_body_atr=1.0,
                                      max_bars_after_signal=5, max_retrace_bars_after_displacement=2),
        )
        v2 = next(e for e in events if e.variant == "V2_FVG_RETRACE")
        self.assertEqual(v2.status, "NO_RETRACE_WITHIN_WINDOW")
        self.assertIsNone(v2.entry_price_proxy)

    def test_incomplete_displacement_window_is_pending_not_a_negative(self):
        rows = [bar(i, 100, 100.2, 99.8, 100) for i in range(16)]
        candidate = signal(rows[14].timestamp_utc)
        events = build_msnr_entry_overlays(
            rows, [candidate],
            config=EntryOverlayConfig(atr_period=5, displacement_body_atr=1.0,
                                      max_bars_after_signal=5, max_retrace_bars_after_displacement=2),
        )
        for variant in ("V1_DISPLACEMENT_CLOSE", "V2_FVG_RETRACE"):
            self.assertEqual(next(e for e in events if e.variant == variant).status,
                             "PENDING_DISPLACEMENT_WINDOW")

    def test_invalid_timestamp_and_config_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "OVERLAY_ATR_PERIOD_INVALID"):
            EntryOverlayConfig(atr_period=1)
        with self.assertRaisesRegex(ValueError, "BAR_TIMESTAMP_MUST_BE_TIMEZONE_AWARE"):
            bad = StrategyBar("2026-11-01T00:00:00", 100, 101, 99, 100)
            build_msnr_entry_overlays([bad], [])


if __name__ == "__main__":
    unittest.main()
