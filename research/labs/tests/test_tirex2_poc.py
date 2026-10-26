from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from research.labs.tirex2_latency_benchmark import (
    is_immutable_commit_sha,
    latency_verdict,
    percentile_ms,
    summarize_latencies,
)
from research.labs.tirex2_synthetic_coupling import (
    SPLITS,
    build_window_pools,
    couple_windows,
    load_series_csv,
    parse_timestamp,
    write_artifacts,
)


class TiRex2SyntheticCouplingTests(unittest.TestCase):
    def make_csv(self, path: Path, *, count: int = 120, symbols=("R_100", "V75", "V100")) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(("timestamp", "symbol", "close", "volume"))
            # Interleave instruments by timestamp. Distinct price paths are not
            # represented as correlated just because a sample later groups them.
            for index in range(count):
                for offset, symbol in enumerate(symbols):
                    writer.writerow((1_800_000_000 + index * 60, symbol, 100 + offset * 20 + index * 0.01, 999999))

    def test_csv_load_and_time_split_prevent_window_crossing(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prices.csv"
            self.make_csv(path)
            series = load_series_csv(path, expected_interval_seconds=60)
            self.assertEqual(sorted(series), ["R_100", "V100", "V75"])
            pools, boundaries = build_window_pools(series, context_length=8, horizon=2)
            self.assertLess(boundaries[0], boundaries[1])
            self.assertEqual(set(pools), set(SPLITS))
            for split in SPLITS:
                samples = couple_windows(pools[split], n_variates=3, sample_count=8, seed=41)
                self.assertEqual(len(samples), 8)
                for sample in samples:
                    self.assertTrue(sample["synthetic_coupling"])
                    self.assertFalse(sample["live_features_permitted"])
                    self.assertEqual(sample["split"], split)
                    variates = sample["variates"]
                    self.assertEqual(len(variates), 3)
                    self.assertEqual(len({v["series_id"] for v in variates}), 3)
                    for variate in variates:
                        self.assertEqual(len(variate["context"]), 8)
                        self.assertEqual(len(variate["target"]), 2)
                        self.assertLessEqual(variate["context_start_ts"], variate["context_end_ts"])
                        self.assertLess(variate["context_end_ts"], variate["target_start_ts"])
                        pool = pools[split][variate["series_id"]]
                        self.assertGreaterEqual(variate["context_start_ts"], pool.data.timestamps[pool.start_index])
                        self.assertLess(variate["target_end_ts"], pool.data.timestamps[pool.end_index - 1] + 60)

    def test_seed_reproduces_samples(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prices.csv"
            self.make_csv(path)
            pools, _ = build_window_pools(load_series_csv(path), context_length=4, horizon=1)
            first = couple_windows(pools["train"], n_variates=2, sample_count=10, seed=123)
            second = couple_windows(pools["train"], n_variates=2, sample_count=10, seed=123)
            self.assertEqual(first, second)

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            csv_path = root / "prices.csv"
            self.make_csv(csv_path)
            pools, boundaries = build_window_pools(load_series_csv(csv_path), context_length=4, horizon=1)
            samples = {split: couple_windows(pools[split], n_variates=2, sample_count=1, seed=7) for split in SPLITS}
            out = root / "out"
            out.mkdir()
            with self.assertRaises(FileExistsError):
                write_artifacts(
                    output_dir=out,
                    input_csv=csv_path,
                    pools=pools,
                    samples_by_split=samples,
                    split_boundaries=boundaries,
                    context_length=4,
                    horizon=1,
                    n_variates=2,
                    seed=7,
                    expected_interval_seconds=60,
                )

    def test_manifest_is_explicitly_research_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            csv_path = root / "prices.csv"
            self.make_csv(csv_path)
            pools, boundaries = build_window_pools(load_series_csv(csv_path), context_length=4, horizon=1)
            samples = {split: couple_windows(pools[split], n_variates=2, sample_count=2, seed=7) for split in SPLITS}
            manifest_path = write_artifacts(
                output_dir=root / "artifacts",
                input_csv=csv_path,
                pools=pools,
                samples_by_split=samples,
                split_boundaries=boundaries,
                context_length=4,
                horizon=1,
                n_variates=2,
                seed=7,
                expected_interval_seconds=60,
            )
            manifest = json.loads(manifest_path.read_text())
            self.assertFalse(manifest["data_policy"]["live_features_permitted"])
            self.assertFalse(manifest["data_policy"]["volume_used"])
            self.assertEqual(manifest["promotion_status"], "RESEARCH_ONLY_NOT_LAYER9_INTEGRATED")
            self.assertEqual(manifest["samples_per_split"], {"train": 2, "validation": 2, "test": 2})

    def test_short_history_reports_no_eligible_windows(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "short.csv"
            self.make_csv(path, count=3)
            series = load_series_csv(path, expected_interval_seconds=60)
            pools, _ = build_window_pools(series, context_length=128, horizon=1)
            with self.assertRaisesRegex(ValueError, "no eligible windows in this split"):
                couple_windows(pools["train"], n_variates=3, sample_count=1)

    def test_coupling_fails_if_not_enough_distinct_series(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "prices.csv"
            self.make_csv(path, symbols=("R_100", "V75"))
            pools, _ = build_window_pools(load_series_csv(path), context_length=4, horizon=1)
            with self.assertRaisesRegex(ValueError, "refusing fallback"):
                couple_windows(pools["train"], n_variates=3, sample_count=1)

    def test_gap_and_non_utc_timestamp_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            gap = Path(temporary) / "gap.csv"
            gap.write_text("timestamp,symbol,close\n1800000000,R_100,100\n1800000120,R_100,101\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected interval"):
                load_series_csv(gap, expected_interval_seconds=60)
            with self.assertRaisesRegex(ValueError, "must include a timezone"):
                parse_timestamp("2026-10-26T08:00:00")
            self.assertEqual(parse_timestamp("2026-10-26T11:00:00+03:00"), parse_timestamp("2026-10-26T08:00:00Z"))


class TiRex2LatencyMetricTests(unittest.TestCase):
    def test_p99_verdict_requires_immutable_revision_and_1000_samples(self):
        smoke_summary = summarize_latencies(list(range(1, 101)))
        self.assertEqual(percentile_ms(list(range(1, 101)), 0.99), 99.0)
        self.assertEqual(smoke_summary["max_ms"], 100.0)
        self.assertEqual(
            latency_verdict(smoke_summary, 99.0, model_revision_pinned=True),
            "NOT_EVALUATED_INSUFFICIENT_SAMPLES",
        )

        summary = summarize_latencies(list(range(1, 1001)))
        self.assertEqual(percentile_ms(list(range(1, 1001)), 0.99), 990.0)
        self.assertEqual(
            latency_verdict(summary, 990.0, model_revision_pinned=True),
            "PASS",
        )
        self.assertEqual(
            latency_verdict(summary, 989.0, model_revision_pinned=True),
            "FAIL",
        )
        self.assertEqual(
            latency_verdict(summary, 990.0, model_revision_pinned=False),
            "NOT_EVALUATED_UNPINNED_MODEL_REVISION",
        )
        self.assertEqual(
            latency_verdict(summary, None, model_revision_pinned=True),
            "NOT_EVALUATED_NO_FROZEN_BUDGET",
        )

    def test_only_full_hex_commit_sha_counts_as_immutable_model_revision(self):
        self.assertTrue(is_immutable_commit_sha("a" * 40))
        self.assertFalse(is_immutable_commit_sha(None))
        self.assertFalse(is_immutable_commit_sha("main"))
        self.assertFalse(is_immutable_commit_sha("a" * 39))
        self.assertFalse(is_immutable_commit_sha("g" * 40))

    def test_invalid_latency_samples_rejected(self):
        with self.assertRaises(ValueError):
            summarize_latencies([])
        with self.assertRaises(ValueError):
            summarize_latencies([1.0, float("nan")])
        with self.assertRaises(ValueError):
            percentile_ms([1.0], 0)


if __name__ == "__main__":
    unittest.main()
