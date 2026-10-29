from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from research.labs.deterministic_intraday_strategies import (
    CAPITAL_AUTHORITY, LIVE_EXECUTION, MSNRConfig, ORBConfig, RegimeConfig,
    StrategyBar, VWAPPullbackConfig, classify_regime, detect_msnr_liquidity_sweep,
    evaluate_opening_range_breakout, evaluate_vwap_pullback,
)


def b(i, o, h, l, c, *, volume=None, session="S1"):
    stamp=(datetime(2026,10,10,tzinfo=timezone.utc)+timedelta(minutes=i)).isoformat()
    return StrategyBar(stamp,o,h,l,c,volume=volume,session_id=session)


def context15m(timestamp="2026-10-09T23:45:00+00:00", o=100, h=101, l=99, c=100.5):
    return StrategyBar(timestamp, o, h, l, c, session_id="M15")


def signal_time_for(rows):
    # StrategyBar timestamps denote candle-open times. Signal at the close of
    # the final fully closed 1-minute bar, which is the next candle's open.
    return (datetime.fromisoformat(rows[-1].timestamp_utc) + timedelta(minutes=1)).isoformat()


def msnr_time_args(rows, *, context=None, signal_time=None):
    return {
        "context_15m_bars": [context15m()] if context is None else context,
        "signal_time_utc": signal_time if signal_time is not None else signal_time_for(rows),
    }


class DeterministicIntradayStrategyTests(unittest.TestCase):
    def test_invalid_bars_and_timestamp_order_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"BAR_HIGH_INCONSISTENT"):
            b(0,10,9,8,9)
        with self.assertRaisesRegex(ValueError,"BAR_TIMESTAMP_MUST_BE_TIMEZONE_AWARE"):
            StrategyBar("2026-10-10T00:00:00",10,11,9,10)
        row=b(0,10,11,9,10)
        with self.assertRaisesRegex(ValueError,"BAR_TIMESTAMPS_MUST_BE_STRICTLY_INCREASING"):
            classify_regime([row,row],config=RegimeConfig(lookback_bars=2))

    def test_regime_requires_history_and_classifies_trend(self):
        rows=[b(i,100+i,101+i,99+i,100.5+i) for i in range(5)]
        cfg=RegimeConfig(lookback_bars=3,trend_efficiency_min=.2,high_volatility_pct=10)
        self.assertIsNone(classify_regime(rows[:3],config=cfg))
        snap=classify_regime(rows,config=cfg)
        self.assertEqual(snap.state,"TRENDING_LOW_VOL")
        self.assertAlmostEqual(snap.directional_efficiency,1.0)

    def test_msnr_bullish_sweep_requires_reclaim_and_structure(self):
        rows=[
            b(0,100,101,99,100),
            b(1,100,100.5,98,99),
            b(2,99,101,98.5,100),
            b(3,100,100.7,99,100),
            b(4,100,101.1,97,100.9),
        ]
        result=detect_msnr_liquidity_sweep(
            rows,config=MSNRConfig(lookback_bars=3,tick_size=.1,min_sweep_ticks=2,max_reclaim_bars=2),
            regime_config=RegimeConfig(lookback_bars=2,high_volatility_pct=10),
            **msnr_time_args(rows),
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.signal_timestamp_utc, signal_time_for(rows))
        self.assertEqual(result.direction,"LONG")
        self.assertEqual(result.target_mode,"OPPOSING_REFERENCE_RANGE_EDGE")
        self.assertFalse(result.capital_authority)
        self.assertFalse(result.order_submission_permitted)
        self.assertIn("M15_CONTEXT_COMPLETED_FRESH", result.evidence_codes)

    def test_msnr_volume_pop_requires_verified_source(self):
        rows=[
            b(0,100,101,99,100,volume=10), b(1,100,100.5,98,99,volume=10),
            b(2,99,101,98.5,100,volume=10), b(3,100,100.7,99,100,volume=9),
            b(4,100,101.1,97,100.9,volume=30),
        ]
        cfg=MSNRConfig(lookback_bars=3,tick_size=.1,min_sweep_ticks=2,max_reclaim_bars=2,
                       require_volume_pop=True,volume_pop_multiplier=1.5)
        regime=RegimeConfig(lookback_bars=2,high_volatility_pct=10)
        self.assertIsNone(detect_msnr_liquidity_sweep(
            rows, config=cfg, regime_config=regime, **msnr_time_args(rows)
        ))
        result=detect_msnr_liquidity_sweep(
            rows, config=cfg, regime_config=regime, volume_source_verified=True,
            **msnr_time_args(rows)
        )
        self.assertIsNotNone(result)
        self.assertIn("VERIFIED_VOLUME_POP",result.evidence_codes)

    def test_msnr_requires_15m_context_and_explicit_signal_boundary(self):
        rows=[b(0,100,101,99,100), b(1,100,100.5,98,99), b(2,99,101,98.5,100),
              b(3,100,100.7,99,100), b(4,100,101.1,97,100.9)]
        cfg=MSNRConfig(lookback_bars=3,tick_size=.1,min_sweep_ticks=2,max_reclaim_bars=2)
        regime=RegimeConfig(lookback_bars=2,high_volatility_pct=10)
        self.assertIsNone(detect_msnr_liquidity_sweep(
            rows, config=cfg, regime_config=regime,
            **msnr_time_args(rows, context=[])))
        self.assertIsNone(detect_msnr_liquidity_sweep(
            rows, config=cfg, regime_config=regime,
            context_15m_bars=[context15m()], signal_time_utc=None))

    def test_msnr_rejects_incomplete_or_stale_15m_context(self):
        rows=[b(0,100,101,99,100), b(1,100,100.5,98,99), b(2,99,101,98.5,100),
              b(3,100,100.7,99,100), b(4,100,101.1,97,100.9)]
        cfg=MSNRConfig(lookback_bars=3,tick_size=.1,min_sweep_ticks=2,max_reclaim_bars=2)
        regime=RegimeConfig(lookback_bars=2,high_volatility_pct=10)
        signal_time = datetime.fromisoformat(signal_time_for(rows))
        incomplete = context15m((signal_time - timedelta(minutes=5)).isoformat())
        stale = context15m((signal_time - timedelta(minutes=35)).isoformat())
        self.assertIsNone(detect_msnr_liquidity_sweep(
            rows, config=cfg, regime_config=regime,
            **msnr_time_args(rows, context=[incomplete])))
        self.assertIsNone(detect_msnr_liquidity_sweep(
            rows, config=cfg, regime_config=regime,
            **msnr_time_args(rows, context=[stale])))

    def test_msnr_does_not_use_target_candle_or_future_context(self):
        rows=[b(0,100,101,99,100), b(1,100,100.5,98,99), b(2,99,101,98.5,100),
              b(3,100,100.7,99,100), b(4,100,101.1,97,100.9)]
        cfg=MSNRConfig(lookback_bars=3,tick_size=.1,min_sweep_ticks=2,max_reclaim_bars=2)
        regime=RegimeConfig(lookback_bars=2,high_volatility_pct=10)
        # Candle 4 opens at 00:04; by that decision boundary its OHLC is not
        # available. Supplying it must be rejected, not treated as a signal.
        self.assertIsNone(detect_msnr_liquidity_sweep(
            rows, config=cfg, regime_config=regime,
            **msnr_time_args(rows, signal_time=rows[-1].timestamp_utc)))
        future_context = context15m("2026-10-10T00:00:00+00:00")
        self.assertIsNone(detect_msnr_liquidity_sweep(
            rows, config=cfg, regime_config=regime,
            **msnr_time_args(rows, context=[future_context])))

    def test_msnr_rejects_missing_trigger_bars(self):
        rows=[b(0,100,101,99,100), b(1,100,100.5,98,99), b(3,99,101,98.5,100),
              b(4,100,100.7,99,100), b(5,100,101.1,97,100.9)]
        cfg=MSNRConfig(lookback_bars=3,tick_size=.1,min_sweep_ticks=2,max_reclaim_bars=2)
        with self.assertRaisesRegex(ValueError, "MSNR_TRIGGER_BAR_INTERVAL_MISMATCH"):
            detect_msnr_liquidity_sweep(
                rows, config=cfg, context_15m_bars=[context15m()],
                signal_time_utc=signal_time_for(rows),
            )

    def test_msnr_rejects_missing_15m_bars_and_invalid_bar_interval(self):
        rows=[b(0,100,101,99,100), b(1,100,100.5,98,99), b(2,99,101,98.5,100),
              b(3,100,100.7,99,100), b(4,100,101.1,97,100.9)]
        cfg=MSNRConfig(lookback_bars=3,tick_size=.1,min_sweep_ticks=2,max_reclaim_bars=2)
        self.assertIsNone(detect_msnr_liquidity_sweep(
            rows, config=cfg, context_15m_bars=[], signal_time_utc=signal_time_for(rows)))
        with self.assertRaisesRegex(ValueError, "MSNR_BAR_INTERVAL_INVALID"):
            MSNRConfig(bar_interval_minutes=0)

    def test_msnr_rejects_duplicate_trigger_timestamps(self):
        rows=[b(0,100,101,99,100), b(1,100,100.5,98,99), b(1,99,101,98.5,100),
              b(3,100,100.7,99,100), b(4,100,101.1,97,100.9)]
        cfg=MSNRConfig(lookback_bars=3,tick_size=.1,min_sweep_ticks=2,max_reclaim_bars=2)
        with self.assertRaisesRegex(ValueError, "BAR_TIMESTAMPS_MUST_BE_STRICTLY_INCREASING"):
            detect_msnr_liquidity_sweep(
                rows, config=cfg, context_15m_bars=[context15m()],
                signal_time_utc=signal_time_for(rows),
            )

    def test_msnr_rejects_duplicate_15m_context_timestamps(self):
        rows=[b(0,100,101,99,100), b(1,100,100.5,98,99), b(2,99,101,98.5,100),
              b(3,100,100.7,99,100), b(4,100,101.1,97,100.9)]
        cfg=MSNRConfig(lookback_bars=3,tick_size=.1,min_sweep_ticks=2,max_reclaim_bars=2)
        context=[context15m(), context15m()]
        with self.assertRaisesRegex(ValueError, "BAR_TIMESTAMPS_MUST_BE_STRICTLY_INCREASING"):
            detect_msnr_liquidity_sweep(
                rows, config=cfg, context_15m_bars=context,
                signal_time_utc=signal_time_for(rows),
            )

    def test_msnr_rejects_out_of_order_15m_context(self):
        rows=[b(0,100,101,99,100), b(1,100,100.5,98,99), b(2,99,101,98.5,100),
              b(3,100,100.7,99,100), b(4,100,101.1,97,100.9)]
        cfg=MSNRConfig(lookback_bars=3,tick_size=.1,min_sweep_ticks=2,max_reclaim_bars=2)
        context=[context15m("2026-10-09T23:45:00+00:00"), context15m("2026-10-09T23:30:00+00:00")]
        with self.assertRaisesRegex(ValueError, "BAR_TIMESTAMPS_MUST_BE_STRICTLY_INCREASING"):
            detect_msnr_liquidity_sweep(
                rows, config=cfg, context_15m_bars=context,
                signal_time_utc=signal_time_for(rows),
            )

    def test_vwap_never_infers_from_unverified_volume(self):
        rows=[b(i,100+i*.1,101+i*.1,99+i*.1,100.5+i*.1,volume=100,session="S1") for i in range(15)]
        cfg=VWAPPullbackConfig(tick_size=.1,trend_lookback_bars=3,volume_contraction_bars=2)
        self.assertIsNone(evaluate_vwap_pullback(rows,config=cfg,volume_source_verified=False))

    def test_vwap_detects_reclaim_using_verified_volume_proxy(self):
        rows=[b(i,100+i*.1,100.5+i*.1,99.7+i*.1,100.2+i*.1,volume=100) for i in range(12)]
        rows[-3]=b(9,101.0,101.2,100.5,100.6,volume=80)
        rows[-2]=b(10,100.6,100.7,100.0,100.2,volume=60)
        rows[-1]=b(11,100.3,101.8,100.0,101.1,volume=55)
        cfg=VWAPPullbackConfig(tick_size=.1,trend_lookback_bars=5,pullback_tolerance_bps=100,volume_contraction_bars=2,
                              allowed_regimes=("TRENDING_LOW_VOL","RANGING_LOW_VOL"))
        result=evaluate_vwap_pullback(rows,config=cfg,
            regime_config=RegimeConfig(lookback_bars=5,high_volatility_pct=10),volume_source_verified=True)
        self.assertIsNotNone(result)
        self.assertEqual(result.direction,"LONG")
        self.assertIn("VWAP_CLOSE_RECLAIM",result.evidence_codes)
        self.assertIn("DOWN_CANDLE_VOLUME_CONTRACTION_PROXY",result.evidence_codes)

    def test_orb_detects_close_confirmed_breakout(self):
        rows=[
            b(0,100,101,99,100), b(1,100,102,99.5,100.7),
            b(2,100.7,101.5,98.5,101.2), b(3,101.2,101.8,100.8,101.5),
            b(4,101.5,102.5,100.8,102.5),
        ]
        cfg=ORBConfig(opening_range_bars=3,tick_size=.1,breakout_buffer_ticks=1,
                      minimum_range_ticks=3,atr_lookback_bars=3,maximum_range_atr_multiple=10)
        reg=RegimeConfig(lookback_bars=2,trend_efficiency_min=.1,high_volatility_pct=10)
        result=evaluate_opening_range_breakout(rows,config=cfg,regime_config=reg)
        self.assertIsNotNone(result)
        self.assertEqual(result.strategy_id,"OPENING_RANGE_BREAKOUT")
        self.assertEqual(result.direction,"LONG")
        self.assertEqual(result.entry_timing,"NEXT_BAR_OPEN_AFTER_SIGNAL")
        self.assertFalse(result.order_submission_permitted)

    def test_orb_requires_explicit_tick_size(self):
        rows=[b(i,100+i,101+i,99+i,100.5+i) for i in range(6)]
        with self.assertRaisesRegex(ValueError,"ORB_TICK_SIZE_REQUIRED"):
            evaluate_opening_range_breakout(rows,config=ORBConfig())

    def test_research_plane_flags_are_non_authoritative(self):
        self.assertFalse(CAPITAL_AUTHORITY)
        self.assertFalse(LIVE_EXECUTION)


if __name__=="__main__":
    unittest.main()
