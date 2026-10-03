import tempfile
import unittest
from pathlib import Path

from research.labs.intraday_bias_measurement import (
    Bar, ForwardObservation, bias_passport, bias_to_execution_command, benjamini_hochberg,
    build_hourly_bars_from_ticks, calculate_statistics, generate_hourly_observations,
)
from research.labs.intraday_bias_archive import append_observations, seal_archive, verify_archive
from research.labs.intraday_bias_cost_model import CostModel, cost_adjusted_statistics
from research.labs.intraday_bias_validation import chronological_split, classify_directional, validate_level1


class IntradayBiasTests(unittest.TestCase):
    def bars(self, n=30):
        return [Bar(f"2026-01-01T{i:02d}:00:00Z", 100.0 + i) for i in range(n)]

    def test_hourly_forward_experiment(self):
        obs = generate_hourly_observations(self.bars(), "TEST")
        self.assertEqual(len(obs), 28)
        self.assertEqual(obs[0].hour_bucket_utc, 0)
        self.assertAlmostEqual(obs[0].raw_return, 1 / 100)

    def test_ticks_build_utc_bars(self):
        ticks = [
            {"timestamp_utc": "2026-01-01T00:01:00Z", "price": 100},
            {"timestamp_utc": "2026-01-01T00:30:00Z", "price": 101},
            {"timestamp_utc": "2026-01-01T01:02:00Z", "price": 102},
        ]
        bars = build_hourly_bars_from_ticks(ticks)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0].open, 100)
        self.assertEqual(bars[0].close, 101)

    def test_gap_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_hourly_observations(
                [Bar("2026-01-01T00:00:00Z", 100), Bar("2026-01-01T02:00:00Z", 101)],
                "TEST",
            )

    def test_statistics(self):
        s = calculate_statistics([0.1, -0.05, 0.05])
        self.assertEqual(s.n, 3)
        self.assertAlmostEqual(s.expectancy, 0.0333333333)
        self.assertGreater(s.profit_factor, 1)

    def test_bh(self):
        q = benjamini_hochberg([0.01, 0.04, 0.5])
        self.assertTrue(all(0 <= x <= 1 for x in q))
        self.assertLessEqual(q[0], q[1])

    def test_passport_cannot_execute(self):
        obs = generate_hourly_observations(self.bars(), "TEST")
        p = bias_passport(
            symbol="TEST", timezone_name="UTC", timeframe="1H", hour_bucket_utc=0,
            observations=obs, is_observations=obs[:14], oos_observations=obs[14:],
        )
        self.assertFalse(p["trade_signal"])
        with self.assertRaises(RuntimeError):
            bias_to_execution_command(p)

    def test_validation_sample_gate(self):
        obs = generate_hourly_observations(self.bars(), "TEST")
        self.assertEqual(
            validate_level1(
                observations=obs, is_observations=obs[:20], oos_observations=obs[20:],
                adjusted_q_value=0.01,
            ),
            "INSUFFICIENT_SAMPLE",
        )

    def test_chronological_split(self):
        obs = generate_hourly_observations(self.bars(), "TEST")
        is_rows, oos_rows = chronological_split(obs, is_end_utc="2026-01-01T00:20:00Z")
        self.assertEqual(len(is_rows) + len(oos_rows), len(obs))
        self.assertLess(is_rows[-1].entry_timestamp_utc, "2026-01-01T00:20:00Z")

    def test_costs_can_erase_drift(self):
        obs = generate_hourly_observations(self.bars(), "TEST")
        raw = calculate_statistics([x.raw_return for x in obs])
        adjusted = cost_adjusted_statistics(obs, CostModel(proportional_cost=0.02))
        self.assertGreater(raw.expectancy, adjusted.expectancy)

    def test_archive_hash_and_seal(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "obs.json"
            append_observations(p, [{"x": 1}])
            self.assertTrue(verify_archive(p))
            seal_archive(p)
            self.assertTrue(verify_archive(p))
            with self.assertRaises(ValueError):
                append_observations(p, [{"x": 2}])

    def test_research_only_constants(self):
        import research.labs.intraday_bias_measurement as m
        self.assertTrue(m.RESEARCH_ONLY)
        self.assertFalse(m.CAPITAL_AUTHORITY)
        self.assertFalse(m.LIVE_EXECUTION)

    def test_bearish_oos_classification_is_possible(self):
        def obs(ret, i):
            return ForwardObservation(
                symbol="TEST", hour_bucket_utc=9,
                signal_timestamp_utc=f"2020-01-01T{i:02d}:00:00Z",
                entry_timestamp_utc=f"2020-01-01T{i:02d}:00:00Z",
                exit_timestamp_utc=f"2020-01-01T{i+1:02d}:00:00Z",
                entry_open=100.0, exit_open=100.0 * (1.0 + ret), raw_return=ret,
            )
        is_rows = [obs(-0.01, i) for i in range(120)]
        oos_rows = [obs(-0.008, i + 120) for i in range(120)]
        self.assertEqual(
            classify_directional(is_observations=is_rows, oos_observations=oos_rows, adjusted_q_value=0.01),
            "ROBUST_BEARISH_PRIOR",
        )


if __name__ == "__main__":
    unittest.main()
