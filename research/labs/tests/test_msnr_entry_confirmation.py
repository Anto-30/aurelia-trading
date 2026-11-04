from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from research.labs.deterministic_intraday_strategies import (
    CycleMarkerConfig,
    MSNRConfirmationConfig,
    RegimeConfig,
    StrategyBar,
    evaluate_msnr_entry_confirmation,
)


def make_bar(index, open_, high, low, close, *, volume=None, start=None, minutes=1):
    origin = start or datetime(2026, 10, 10, tzinfo=timezone.utc)
    stamp = origin + timedelta(minutes=index * minutes)
    return StrategyBar(stamp.isoformat(), open_, high, low, close, volume=volume)


def msnr_bars(*, volume=100.0):
    rows = [
        make_bar(i, 100.0, 101.0, 99.0, 100.0, volume=volume)
        for i in range(20)
    ]
    rows.append(make_bar(20, 100.0, 100.5, 96.9, 100.0, volume=151.0))
    return rows


def htf_bars(direction="down"):
    origin = datetime(2026, 10, 9, 10, tzinfo=timezone.utc)
    rows = []
    for i in range(55):
        close = 100.0 + (i * 0.1 if direction == "up" else -i * 0.1)
        rows.append(make_bar(
            i, close, close + 0.5, close - 0.5, close,
            start=origin, minutes=15,
        ))
    return rows


class MSNRConfirmationTests(unittest.TestCase):
    def config(self, **kwargs):
        fields = dict(
            timeframe="1m",
            lookback_bars=20,
            atr_period=14,
            min_sweep_atr=1.0,
            rejection_close_fraction=0.60,
            tick_size=0.1,
            require_volume_confirmation=False,
            volume_sma_period=20,
            volume_multiplier=1.5,
            require_htf_alignment=False,
            htf_ema_period=50,
            htf_slope_lookback=5,
        )
        fields.update(kwargs)
        return MSNRConfirmationConfig(**fields)

    def test_detects_atr_sweep_with_sixty_percent_rejection_and_range_reclaim(self):
        verdict = evaluate_msnr_entry_confirmation(
            msnr_bars(),
            config=self.config(),
            regime_config=RegimeConfig(lookback_bars=10, high_volatility_pct=10),
        )
        self.assertTrue(verdict.signal_valid)
        self.assertEqual(verdict.direction, "LONG")
        self.assertEqual(verdict.reason, "PASSED")
        self.assertIn("ATR_SWEEP_CONFIRMED", verdict.evidence_codes)
        self.assertIn("REJECTION_CLOSE_INWARD_CONFIRMED", verdict.evidence_codes)
        self.assertFalse(verdict.capital_authority)
        self.assertFalse(verdict.order_submission_permitted)

    def test_rejects_breach_smaller_than_one_atr(self):
        rows = msnr_bars()
        rows[-1] = make_bar(20, 100.0, 100.5, 97.1, 100.0, volume=151)
        verdict = evaluate_msnr_entry_confirmation(
            rows, config=self.config(),
            regime_config=RegimeConfig(lookback_bars=10, high_volatility_pct=10),
        )
        self.assertFalse(verdict.signal_valid)
        self.assertEqual(verdict.reason, "NO_ATR_SIZED_LIQUIDITY_SWEEP")

    def test_rejects_weak_rejection_close_or_close_outside_prior_range(self):
        rows = msnr_bars()
        rows[-1] = make_bar(20, 100.0, 100.5, 96.9, 97.5, volume=151)
        verdict = evaluate_msnr_entry_confirmation(
            rows, config=self.config(),
            regime_config=RegimeConfig(lookback_bars=10, high_volatility_pct=10),
        )
        self.assertFalse(verdict.signal_valid)
        self.assertEqual(verdict.reason, "REJECTION_CLOSE_NOT_BACK_INSIDE_RANGE")

    def test_volume_confirmation_requires_verified_volume_provenance(self):
        cfg = self.config(require_volume_confirmation=True)
        kwargs = dict(
            bars=msnr_bars(),
            config=cfg,
            regime_config=RegimeConfig(lookback_bars=10, high_volatility_pct=10),
        )
        unverified = evaluate_msnr_entry_confirmation(**kwargs, volume_source_verified=False)
        self.assertFalse(unverified.signal_valid)
        self.assertEqual(unverified.reason, "VOLUME_SOURCE_UNVERIFIED")
        verified = evaluate_msnr_entry_confirmation(**kwargs, volume_source_verified=True)
        self.assertTrue(verified.signal_valid)
        self.assertIn("VERIFIED_VOLUME_SMA_POP", verified.evidence_codes)

    def test_htf_filter_rejects_long_setup_against_falling_ema50(self):
        verdict = evaluate_msnr_entry_confirmation(
            msnr_bars(),
            config=self.config(require_htf_alignment=True),
            regime_config=RegimeConfig(lookback_bars=10, high_volatility_pct=10),
            higher_timeframe_bars=htf_bars("down"),
        )
        self.assertFalse(verdict.signal_valid)
        self.assertEqual(verdict.reason, "HTF_STRUCTURE_OPPOSED")

    def test_htf_filter_rejects_missing_or_future_htf_data(self):
        no_htf = evaluate_msnr_entry_confirmation(
            msnr_bars(),
            config=self.config(require_htf_alignment=True),
            regime_config=RegimeConfig(lookback_bars=10, high_volatility_pct=10),
        )
        self.assertFalse(no_htf.signal_valid)
        self.assertEqual(no_htf.reason, "HTF_DATA_UNAVAILABLE")
        future_rows = htf_bars("up")
        future_rows[-1] = make_bar(
            54, 100, 101, 99, 100,
            start=datetime(2026, 10, 10, 1, tzinfo=timezone.utc),
            minutes=15,
        )
        future = evaluate_msnr_entry_confirmation(
            msnr_bars(),
            config=self.config(require_htf_alignment=True),
            regime_config=RegimeConfig(lookback_bars=10, high_volatility_pct=10),
            higher_timeframe_bars=future_rows,
        )
        self.assertFalse(future.signal_valid)
        self.assertEqual(future.reason, "HTF_DATA_NOT_CLOSED_BEFORE_SIGNAL")

    def test_cycle_marker_is_disabled_for_247_synthetic_indices_by_default(self):
        verdict = evaluate_msnr_entry_confirmation(
            msnr_bars(),
            config=self.config(),
            regime_config=RegimeConfig(lookback_bars=10, high_volatility_pct=10),
        )
        self.assertTrue(verdict.signal_valid)
        self.assertNotIn("CYCLE_MARKER", verdict.evidence_codes)

    def test_clock_fixed_marker_uses_new_york_wall_clock_on_est_day(self):
        signal_time = datetime(2026, 11, 4, 8, 49, 55, tzinfo=ZoneInfo("America/New_York"))
        cycle = CycleMarkerConfig(
            enabled=True,
            normalization="clock_fixed",
            dst_transition_policy="apply_local_timezone",
        )
        verdict = evaluate_msnr_entry_confirmation(
            msnr_bars(),
            config=self.config(temporal_required=True),
            regime_config=RegimeConfig(lookback_bars=10, high_volatility_pct=10),
            signal_time=signal_time,
            cycle_config=cycle,
        )
        self.assertTrue(verdict.signal_valid)
        self.assertIn("CYCLE_MARKER_WINDOW_CONFIRMED", verdict.evidence_codes)

    def test_enabled_cycle_marker_fails_closed_without_dst_normalization_rule(self):
        verdict = evaluate_msnr_entry_confirmation(
            msnr_bars(),
            config=self.config(temporal_required=True),
            regime_config=RegimeConfig(lookback_bars=10, high_volatility_pct=10),
            signal_time=datetime(2026, 11, 4, 13, 49, 55, tzinfo=timezone.utc),
            cycle_config=CycleMarkerConfig(enabled=True),
        )
        self.assertFalse(verdict.signal_valid)
        self.assertEqual(verdict.reason, "CYCLE_DST_NORMALIZATION_UNSPECIFIED")

    def test_cycle_marker_enforces_hard_cutoff(self):
        cycle = CycleMarkerConfig(
            enabled=True,
            normalization="clock_fixed",
            dst_transition_policy="apply_local_timezone",
        )
        signal_time = datetime(2026, 11, 4, 8, 51, 26, tzinfo=ZoneInfo("America/New_York"))
        verdict = evaluate_msnr_entry_confirmation(
            msnr_bars(),
            config=self.config(temporal_required=True),
            regime_config=RegimeConfig(lookback_bars=10, high_volatility_pct=10),
            signal_time=signal_time,
            cycle_config=cycle,
        )
        self.assertFalse(verdict.signal_valid)
        self.assertEqual(verdict.reason, "TEMPORAL_HARD_CUTOFF_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
