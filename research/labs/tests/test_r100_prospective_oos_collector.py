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
    quoted_contract_economics,
    evaluation,
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


    def test_quoted_binary_contract_economics(self):
        observations = [
            {"signal_id": "a", "outcome": 1},
            {"signal_id": "b", "outcome": 0},
        ]
        quotes = [
            {"signal_id": "a", "ask_price": 1.0, "payout": 1.95, "quote_status": "OBSERVED"},
            {"signal_id": "b", "ask_price": 1.0, "payout": 1.95, "quote_status": "OBSERVED"},
        ]
        economics = quoted_contract_economics(observations, quotes)
        self.assertEqual(economics["sample_count"], 2)
        self.assertAlmostEqual(economics["win_rate"], 0.5)
        self.assertAlmostEqual(economics["mean_net_return_per_stake"], -0.025)
        self.assertAlmostEqual(economics["break_even_probability"], 1 / 1.95)

    def test_oos_uses_direction_adjusted_strategy_return(self):
        state = initial_state()
        start = state["manifest"]["oos_start_at_utc"]
        state["observations"] = [
            {
                "signal_id": "call",
                "direction": "CALL",
                "raw_return": 0.01,
                "outcome": 1,
                "probability": 0.60,
                "signal_timestamp_utc": start,
            },
            {
                "signal_id": "put",
                "direction": "PUT",
                "raw_return": 0.01,
                "outcome": 0,
                "probability": 0.60,
                "signal_timestamp_utc": start,
            },
        ]
        report = evaluation(state)
        self.assertAlmostEqual(report["oos_mean_market_return"], 0.01)
        self.assertAlmostEqual(report["oos_mean_strategy_return"], 0.0)
        self.assertEqual(report["qualification_status"], "INSUFFICIENT_SAMPLE")

    def test_horizon_is_positive(self):
        self.assertGreater(HORIZON_TICKS, 0)


if __name__ == "__main__":
    unittest.main()
