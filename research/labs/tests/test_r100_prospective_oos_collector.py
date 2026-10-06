from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from research.r100_prospective_oos_collector import (
    HORIZON_TICKS,
    STRATEGY_ID,
    build_signal_id,
    initial_state,
    probability_metrics,
    save_state,
    load_state,
)


class R100ProspectiveCollectorTest(unittest.TestCase):
    def test_manifest_is_frozen_and_non_authorizing(self):
        state = initial_state()
        manifest = state["manifest"]
        self.assertEqual(manifest["strategy_id"], STRATEGY_ID)
        self.assertEqual(manifest["trial_count"], 1)
        self.assertEqual(manifest["search_degrees_of_freedom"], 0)
        self.assertEqual(manifest["oos_reuse_count"], 0)
        self.assertFalse(manifest["sealed"])
        self.assertEqual(
            manifest["regime_policy"],
            "single predeclared ALL_MARKET cell; no data-mined regime segmentation in this campaign",
        )

    def test_probability_metrics(self):
        rows = [
            {"probability": 0.55, "outcome": 1},
            {"probability": 0.60, "outcome": 0},
            {"probability": 0.65, "outcome": 1},
            {"probability": 0.70, "outcome": 1},
            {"probability": 0.75, "outcome": 0},
            {"probability": 0.55, "outcome": 0},
        ]
        metrics = probability_metrics(rows)
        self.assertEqual(metrics["sample_count"], 6)
        self.assertGreaterEqual(metrics["brier_score"], 0.0)
        self.assertGreaterEqual(metrics["log_loss"], 0.0)
        self.assertIsInstance(metrics["reliability_buckets"], list)

    def test_probability_policy_is_not_clipped_outside_range(self):
        self.assertFalse(0.54 >= 0.55 and 0.54 <= 0.75)
        self.assertFalse(0.76 >= 0.55 and 0.76 <= 0.75)

    def test_signal_id_is_deterministic(self):
        timestamp = "2026-10-06T20:00:00Z"
        self.assertEqual(
            build_signal_id(timestamp, 100.0, "CALL"),
            build_signal_id(timestamp, 100.0, "CALL"),
        )

    def test_state_round_trip_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = initial_state()
            save_state(path, state)
            restored = load_state(path)
            self.assertEqual(restored["schema"], "aurelia.r100.prospective_oos.v1")
            self.assertEqual(restored["manifest"]["strategy_version"], "0.2.0")
            self.assertEqual(restored["observations"], [])

    def test_horizon_is_positive(self):
        self.assertGreater(HORIZON_TICKS, 0)


if __name__ == "__main__":
    unittest.main()
