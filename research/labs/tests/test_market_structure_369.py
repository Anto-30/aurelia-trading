from __future__ import annotations
import asyncio
import math
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from research.labs.market_structure_369 import CAPITAL_AUTHORITY, LIVE_EXECUTION, NY_AM_SESSION, ORDER_SUBMISSION_PERMITTED, RESEARCH_ONLY, CandidateSetup, DerivHistoryManifest, ExperimentDataset, FairValueGap, Instrument369Spec, detect_m15_sweeps, ProtectedSwing, SessionWindow, StructureBreak, _block_bootstrap, StructureConfig, SweepEvent, TradeRecord, _simulate_setup, ExperimentConfig, TRADE_COLUMNS, active_fvgs_at, build_trade_frame, calculate_369_step, calculate_atr, detect_protected_swings, fetch_deriv_history, find_m1_mss_after_sweep, is_in_session, is_price_at_369_level, normalize_deriv_candle_payload, project_369_levels, scan_and_track_fvgs, validate_experiment_dataset, validate_trade_frame
UTC = timezone.utc
BASE_EPOCH = 1800000000

def bar(i, o, h, l, c, *, base=None, interval=60, synthetic=False):
    origin = base or datetime(2026, 10, 10, tzinfo=UTC)
    stamp = origin + timedelta(seconds=i * interval)
    from research.labs.market_structure_369 import OHLCBar
    return OHLCBar(stamp.isoformat(), o, h, l, c, synthetic=synthetic)

def structure_fixture(*, strong_break=True):
    rows = [bar(i, 100, 101, 99, 100) for i in range(10)]
    candles = [(100, 102, 99, 101), (101, 105, 100, 104), (103, 104, 99, 100), (100, 102, 97, 98), (98, 101, 98, 100), (100, 102, 99, 101), (101, 103, 100, 102), (101, 102, 99, 100), (100, 103, 99, 102), (101, 102, 100, 101), (101, 102, 100, 101), (101, 110, 100, 108) if strong_break else (103, 105, 103, 104)]
    rows.extend((bar(10 + i, *c) for i, c in enumerate(candles)))
    return rows

def trade(group='Control'):
    return TradeRecord(f'{group.lower()}-trade-001', group, 'R_100', 'LONG', '2026-10-10T00:10:00Z', '2026-10-10T00:10:00Z', '2026-10-10T00:12:00Z', '2026-10-10T00:13:00Z', '2026-10-10T00:14:00Z', '2026-10-10T00:16:00Z', 100.0, 99.0, 102.0, 102.0, 2.0, None, 'TAKE_PROFIT', 98.0, group == 'Test_369', 'a' * 64)

class ProtectedSwingTests(unittest.TestCase):
    def test_detect_protected_swing(self):
        events = detect_protected_swings(structure_fixture())
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual((event.direction, event.break_index), ('LONG', 21))
        self.assertEqual(event.broken_swing_index, 11)
        self.assertEqual(event.protected_swing.swing_index, 13)
        self.assertEqual(event.protected_swing.price, 97.0)
        self.assertGreater(event.displacement_ratio, 1.5)
    def test_small_body_break_rejected(self):
        self.assertEqual(detect_protected_swings(structure_fixture(strong_break=False)), [])
    def test_weak_cross_cannot_be_retroactively_upgraded(self):
        rows = structure_fixture()[:-1]
        rows.append(bar(21, 104, 106, 103, 105.5))
        rows.append(bar(22, 105.5, 115, 105, 113))
        self.assertEqual(detect_protected_swings(rows), [])
    def test_bearish_protected_swing_is_symmetric(self):
        bullish = structure_fixture()
        mirrored = [bar(i, 200 - x.open, 200 - x.low, 200 - x.high, 200 - x.close) for i, x in enumerate(bullish)]
        events = detect_protected_swings(mirrored)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].direction, 'SHORT')
        self.assertEqual(events[0].protected_swing.swing_type, 'high')
        self.assertEqual(events[0].protected_swing.price, 103.0)
    def test_atr_excludes_current_candle(self):
        rows = structure_fixture()
        before = calculate_atr(rows, 21)
        rows[21] = bar(21, 101, 1000, 1, 999)
        self.assertEqual(calculate_atr(rows, 21), before)
    def test_atr_does_not_bridge_a_gap_before_the_window(self):
        rows = structure_fixture()
        old = rows[10]
        rows[10] = type(old)((old.timestamp + timedelta(minutes=1)).isoformat(), old.open, old.high, old.low, old.close)
        self.assertIsNone(calculate_atr(rows, 21))
    def test_gap_resets_structure_state(self):
        rows = structure_fixture()
        for i in range(17, len(rows)):
            old = rows[i]
            rows[i] = type(old)((old.timestamp + timedelta(minutes=1)).isoformat(), old.open, old.high, old.low, old.close)
        self.assertEqual(detect_protected_swings(rows), [])

class M15SweepTests(unittest.TestCase):
    def test_protected_low_sweep_requires_wick_through_and_reclaim(self):
        rows = structure_fixture()
        m15 = [bar(i, x.open, x.high, x.low, x.close, interval=900) for i, x in enumerate(rows)]
        m15.append(bar(22, 98, 99, 96, 98, interval=900))
        events = detect_m15_sweeps(m15)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].direction, 'LONG')
        self.assertEqual(events[0].sweep_extreme, 96.0)
        self.assertEqual(events[0].reference_swing_price, 97.0)

class FVGTests(unittest.TestCase):
    def test_fvg_midpoint_mitigation(self):
        base = datetime(2026, 10, 10, tzinfo=UTC)
        rows = [bar(0, 10, 11, 9, 10, base=base), bar(1, 11.5, 13, 11.5, 12.5, base=base), bar(2, 14.5, 16, 14, 15.5, base=base), bar(3, 14.5, 15, 13, 14, base=base), bar(4, 13, 14, 12.4, 12.8, base=base)]
        active = active_fvgs_at(rows[:4], 3)
        self.assertTrue(any(g.created_index == 2 and g.bottom == 11 and g.top == 14 for g in active))
        gap = next((g for g in scan_and_track_fvgs(rows) if g.created_index == 2))
        self.assertEqual((gap.direction, gap.bottom, gap.top, gap.midpoint), ('LONG', 11, 14, 12.5))
        self.assertTrue(gap.is_mitigated)
        self.assertEqual(gap.mitigated_index, 4)
    def test_equal_boundary_is_not_gap(self):
        rows = [bar(0, 10, 11, 9, 10), bar(1, 11, 12, 10, 11), bar(2, 12, 13, 11, 12)]
        self.assertEqual(scan_and_track_fvgs(rows), [])
    def test_gap_makes_active_fvg_stale_not_active(self):
        rows = [bar(0, 10, 11, 9, 10), bar(1, 11.5, 13, 11.5, 12.5), bar(2, 14.5, 16, 14, 15.5), bar(4, 14, 15, 13, 14)]
        gap = next((g for g in scan_and_track_fvgs(rows) if g.created_index == 2))
        self.assertTrue(gap.is_stale)
        self.assertFalse(gap.is_active)

class SessionTests(unittest.TestCase):
    def test_ny_session_boundaries_across_dst(self):
        self.assertTrue(is_in_session('2026-10-30T11:20:00Z'))
        self.assertTrue(is_in_session('2026-10-30T14:45:00Z'))
        self.assertFalse(is_in_session('2026-10-30T14:46:00Z'))
        self.assertTrue(is_in_session('2026-11-02T12:20:00Z'))
        self.assertTrue(is_in_session('2026-11-02T15:45:00Z'))
        self.assertFalse(is_in_session('2026-11-02T15:46:00Z'))
        self.assertFalse(is_in_session('2026-11-02T12:19:00Z'))
    def test_london_is_explicitly_configurable(self):
        from datetime import time
        london = SessionWindow('LONDON_AM', 'Europe/London', time(7, 20), time(10, 45))
        self.assertTrue(london.contains('2026-10-23T06:20:00Z'))
        self.assertTrue(london.contains('2026-10-30T07:20:00Z'))
        self.assertFalse(london.contains('2026-10-30T10:46:00Z'))
        self.assertEqual(NY_AM_SESSION.name, 'NY_AM')

class M1MSSWindowTests(unittest.TestCase):
    def sweep(self, timestamp):
        protected = ProtectedSwing(4, 6, 10, 97.0, 'low', 'LONG', 105.0, 2.0)
        return SweepEvent(0, timestamp, 'LONG', 96.0, protected)
    def test_mss_detected_only_inside_n_bars(self):
        rows = structure_fixture()
        hit = find_m1_mss_after_sweep(rows, self.sweep('2026-10-10T00:15:00Z'), n_bars=10)
        self.assertIsNotNone(hit)
        self.assertEqual(hit.break_index, 21)
        self.assertIsNone(find_m1_mss_after_sweep(rows, self.sweep('2026-10-10T00:15:00Z'), n_bars=6))
    def test_sweep_extreme_invalidation_cancels_setup(self):
        rows = structure_fixture()
        rows[18] = bar(18, 98, 99, 90, 95)
        self.assertIsNone(find_m1_mss_after_sweep(rows, self.sweep('2026-10-10T00:15:00Z'), n_bars=10))
    def test_missing_first_m1_candle_does_not_expand_n_bar_window(self):
        rows = structure_fixture()
        shifted = []
        for i, item in enumerate(rows):
            if i >= 15:
                item = type(item)((item.timestamp + timedelta(minutes=1)).isoformat(), item.open, item.high, item.low, item.close)
            shifted.append(item)
        self.assertIsNone(find_m1_mss_after_sweep(shifted, self.sweep('2026-10-10T00:15:00Z'), n_bars=10))

class ThreeSixNineTests(unittest.TestCase):
    def test_calculate_369_step(self):
        self.assertEqual(calculate_369_step(4217.395), 15.0)
        self.assertEqual(calculate_369_step(4023.0), 18.0)
        self.assertEqual(calculate_369_step(25417.35), 12.0)
        self.assertEqual(calculate_369_step(5.0), 15.0)
        self.assertEqual(calculate_369_step(9.0), 18.0)
        with self.assertRaisesRegex(ValueError, '369_REFERENCE_PRICE_INVALID'):
            calculate_369_step(-1)
        with self.assertRaisesRegex(ValueError, '369_REFERENCE_PRICE_INVALID'):
            calculate_369_step(0)
        with self.assertRaisesRegex(ValueError, '369_NORMALIZED_PRICE_MUST_BE_AT_LEAST_ONE'):
            calculate_369_step(0.5)
    def test_xauusd_and_nq_scaling_is_injected_not_guessed(self):
        xau = Instrument369Spec('XAUUSD', 0.1, 0.1, 0.01)
        nq = Instrument369Spec('NQ', 1.0, 0.25, 0.25)
        self.assertEqual(calculate_369_step(2350, price_quantum=xau.price_quantum, step_unit=xau.step_unit), 1.2)
        self.assertEqual(calculate_369_step(21000, price_quantum=nq.price_quantum, step_unit=nq.step_unit), 4.5)
    def test_projection_uses_exact_protected_swing(self):
        spec = Instrument369Spec('NQ', 1, 0.25, 0.25, 1)
        levels = project_369_levels(1000, spec, levels_each_side=2)
        self.assertIn(1003.0, levels)
        self.assertTrue(is_price_at_369_level(1003.0, 1000, spec))
        self.assertFalse(is_price_at_369_level(1000, 1000, spec))
        self.assertFalse(is_price_at_369_level(1004.0, 1000, spec))

class DerivPipelineTests(unittest.TestCase):
    def payload(self, epochs):
        return {'echo_req': {'ticks_history': 'R_100', 'style': 'candles', 'granularity': 60}, 'msg_type': 'candles', 'candles': [{'epoch': e, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5} for e in epochs]}
    def test_deriv_api_pipeline(self):
        epochs = [BASE_EPOCH, BASE_EPOCH + 60, BASE_EPOCH + 180]
        dropped = normalize_deriv_candle_payload(self.payload(epochs), symbol='R_100', granularity_seconds=60, start_epoch=BASE_EPOCH, end_epoch=BASE_EPOCH + 180, missing_policy='drop')
        self.assertEqual([int(b.timestamp.timestamp()) for b in dropped], epochs)
        filled = normalize_deriv_candle_payload(self.payload(epochs), symbol='R_100', granularity_seconds=60, missing_policy='forward_fill')
        self.assertEqual(len(filled), 4)
        self.assertTrue(filled[2].synthetic)
        self.assertEqual(int(filled[2].timestamp.timestamp()), BASE_EPOCH + 120)
        trailing = normalize_deriv_candle_payload(self.payload([BASE_EPOCH, BASE_EPOCH + 60]), symbol='R_100', granularity_seconds=60, end_epoch=BASE_EPOCH + 180, missing_policy='forward_fill')
        self.assertEqual(len(trailing), 4)
        self.assertTrue(trailing[-1].synthetic)
        with self.assertRaisesRegex(ValueError, 'DERIV_DUPLICATE_CANDLE_EPOCH'):
            normalize_deriv_candle_payload(self.payload([BASE_EPOCH, BASE_EPOCH]), symbol='R_100', granularity_seconds=60)
        with self.assertRaisesRegex(ValueError, 'DERIV_CANDLE_EPOCH_NOT_ALIGNED_TO_GRANULARITY'):
            normalize_deriv_candle_payload(self.payload([BASE_EPOCH, BASE_EPOCH + 90]), symbol='R_100', granularity_seconds=60)
    def test_source_verified_requires_explicit_attestation(self):
        async def request(_args):
            return self.payload([BASE_EPOCH])
        with self.assertRaisesRegex(ValueError, 'DERIV_SOURCE_ATTESTATION_INCOMPLETE'):
            asyncio.run(fetch_deriv_history(request, symbol='R_100', start_epoch=BASE_EPOCH, end_epoch=BASE_EPOCH + 60, granularity_seconds=60, source_verified=True))
    def test_deriv_history_paging_is_read_only_and_not_self_verified(self):
        calls = []
        async def request(args):
            calls.append(dict(args))
            start, end = (int(args['start']), int(args['end']))
            return {'echo_req': {'ticks_history': 'R_100', 'style': 'candles', 'granularity': 60}, 'msg_type': 'candles', 'candles': [{'epoch': t, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5} for t in range(start, end + 1, 60)]}
        result = asyncio.run(fetch_deriv_history(request, symbol='R_100', start_epoch=BASE_EPOCH, end_epoch=BASE_EPOCH + 180, granularity_seconds=60, batch_count=2))
        self.assertEqual(len(result.bars), 4)
        self.assertEqual(result.manifest.request_count, 2)
        self.assertFalse(result.manifest.source_verified)
        self.assertEqual(len(result.manifest.content_sha256), 64)
        self.assertTrue(all(('subscribe' not in x and 'count' not in x for x in calls)))
        self.assertEqual(len(result.manifest.acquisition_evidence_sha256 or ''), 64)
        async def request_with_gap(args):
            start, end = (int(args['start']), int(args['end']))
            epochs = [start, start + 120]
            return {'echo_req': {'ticks_history': 'R_100', 'style': 'candles', 'granularity': 60}, 'msg_type': 'candles', 'candles': [{'epoch': t, 'open': 100, 'high': 101, 'low': 99, 'close': 100.5} for t in epochs]}
        filled_result = asyncio.run(fetch_deriv_history(request_with_gap, symbol='R_100', start_epoch=BASE_EPOCH, end_epoch=BASE_EPOCH + 120, granularity_seconds=60, batch_count=3, missing_policy='forward_fill'))
        self.assertEqual(len(filled_result.bars), 3)
        self.assertTrue(filled_result.bars[1].synthetic)

class TradeSimulationTests(unittest.TestCase):
    def _setup(self):
        protected = ProtectedSwing(0, 0, 0, 9.0, 'low', 'LONG', 13.0, 2.0)
        sweep = SweepEvent(0, '2026-10-10T00:01:00Z', 'LONG', 9.0, protected)
        mss = StructureBreak(1, '2026-10-10T00:02:00Z', 'LONG', 1, 13.0, protected, 4.0, 2.0, 2.0)
        fvg = FairValueGap(2, '2026-10-10T00:03:00Z', 14.0, 11.0, 12.5, 'LONG')
        return CandidateSetup(sweep, mss, fvg, 3, 12.5, False)
    def test_entry_candle_target_touch_is_not_assumed_post_fill(self):
        rows = [bar(0, 10, 11, 9, 10), bar(1, 11.5, 13, 11.5, 12.5), bar(2, 14.5, 16, 14, 15.5), bar(3, 13, 20, 12.4, 14), bar(4, 14, 14.5, 13, 14.2)]
        record = _simulate_setup(rows, self._setup(), group='Control', symbol='X', dataset_sha256='b' * 64, max_holding_bars=2, take_profit_r=2.0, cost_per_trade_r=None)
        self.assertEqual(record.exit_reason, 'TIME_EXIT')
        self.assertAlmostEqual(record.r_multiple, (14.2 - 12.5) / 1.5)
    def test_entry_candle_stop_touch_is_conservatively_counted(self):
        rows = [bar(0, 10, 11, 9, 10), bar(1, 11.5, 13, 11.5, 12.5), bar(2, 14.5, 16, 14, 15.5), bar(3, 13, 20, 10.5, 14)]
        record = _simulate_setup(rows, self._setup(), group='Control', symbol='X', dataset_sha256='b' * 64, max_holding_bars=2, take_profit_r=2.0, cost_per_trade_r=None)
        self.assertEqual(record.exit_reason, 'STOP_LOSS')
        self.assertEqual(record.r_multiple, -1.0)
    def test_stop_is_buffered_beyond_fvg_invalidation(self):
        rows = [bar(0, 10, 11, 9, 10), bar(1, 11.5, 13, 11.5, 12.5), bar(2, 14.5, 16, 14, 15.5), bar(3, 13, 13.5, 12.4, 13), bar(4, 13, 14.5, 13, 14.2)]
        record = _simulate_setup(rows, self._setup(), group='Control', symbol='X', dataset_sha256='b' * 64, max_holding_bars=2, take_profit_r=2.0, cost_per_trade_r=None, stop_buffer_price=0.1)
        self.assertAlmostEqual(record.stop_loss, 10.9)
        self.assertAlmostEqual(record.take_profit, 15.7)

class BootstrapTests(unittest.TestCase):
    def test_block_length_uses_calendar_days_not_only_trade_days(self):
        control = [replace(trade('Control'), exit_timestamp_utc=f'2026-10-{day:02d}T12:00:00Z') for day in (1, 11)]
        test_rows = [replace(trade('Test_369'), exit_timestamp_utc=f'2026-10-{day:02d}T12:00:00Z') for day in (1, 11)]
        result = _block_bootstrap(control, test_rows, iterations=2000, block_days=5, confidence_level=0.95, seed=369)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result['replicates'], 1000)

class InstitutionalSchemaTests(unittest.TestCase):
    def test_decision_gate_cannot_be_weakened_below_registered_thresholds(self):
        spec = Instrument369Spec('R_100', 1, 1, 0.01)
        with self.assertRaisesRegex(ValueError, 'EXPERIMENT_DECISION_THRESHOLD_BELOW_REGISTERED_GATE'):
            ExperimentConfig('R_100', spec, 10, 60, minimum_test_trades=200)
        with self.assertRaisesRegex(ValueError, 'EXPERIMENT_DECISION_THRESHOLD_BELOW_REGISTERED_GATE'):
            ExperimentConfig('R_100', spec, 10, 60, minimum_expectancy_improvement_r=0.05)
    def test_trade_frame_strict_columns_and_critical_nulls(self):
        frame = build_trade_frame([trade()])
        self.assertEqual(tuple(frame.columns), TRADE_COLUMNS)
        bad = frame.copy()
        bad.loc[0, 'r_multiple'] = math.nan
        with self.assertRaisesRegex(ValueError, 'TRADE_FRAME_CRITICAL_NULL'):
            validate_trade_frame(bad)
    def test_dataset_fails_closed_when_source_not_verified(self):
        m1 = [bar(0, 100, 101, 99, 100), bar(1, 100, 101, 99, 100)]
        m15 = [bar(0, 100, 101, 99, 100, interval=900), bar(1, 100, 101, 99, 100, interval=900)]
        man1 = DerivHistoryManifest('Deriv', 'R_100', 60, 0, 60, '', 1, 'https://developers.deriv.com/docs/data/ticks-history/', False)
        man15 = DerivHistoryManifest('Deriv', 'R_100', 900, 0, 900, '', 1, 'https://developers.deriv.com/docs/data/ticks-history/', False)
        with self.assertRaisesRegex(ValueError, 'DERIV_SOURCE_VERIFICATION_REQUIRED'):
            validate_experiment_dataset(m1, m15, ExperimentDataset('R_100', man1, man15))
    def test_research_flags_have_no_capital_authority(self):
        self.assertTrue(RESEARCH_ONLY)
        self.assertFalse(CAPITAL_AUTHORITY)
        self.assertFalse(LIVE_EXECUTION)
        self.assertFalse(ORDER_SUBMISSION_PERMITTED)
if __name__ == '__main__':
    unittest.main()
