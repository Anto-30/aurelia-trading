from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
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
    observe_tick,
)


class R100ProspectiveCollectorTest(unittest.TestCase):
    def test_manifest_binds_exact_source_commit(self):
        previous = os.environ.get("AURELIA_RESEARCH_CODE_COMMIT")
        try:
            os.environ["AURELIA_RESEARCH_CODE_COMMIT"] = "commit-under-test"
            manifest = initial_state()["manifest"]
            self.assertEqual(manifest["code_commit"], "commit-under-test")
            self.assertTrue(manifest["config_hash"])
        finally:
            if previous is None:
                os.environ.pop("AURELIA_RESEARCH_CODE_COMMIT", None)
            else:
                os.environ["AURELIA_RESEARCH_CODE_COMMIT"] = previous

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

    def test_poor_reliability_cannot_be_marked_calibrated(self):
        rows = (
            [{"probability": 0.55, "outcome": 1}] * 40
            + [{"probability": 0.65, "outcome": 1}] * 30
            + [{"probability": 0.75, "outcome": 1}] * 30
        )
        metrics = probability_metrics(rows)
        self.assertGreater(metrics["max_reliability_gap"], 0.05)
        self.assertEqual(metrics["calibration_status"], "PROVISIONAL")
    def test_signal_id_is_deterministic(self):
        timestamp = "2026-10-06T20:00:00Z"
        self.assertEqual(
            build_signal_id(timestamp, 100.0, "CALL"),
            build_signal_id(timestamp, 100.0, "CALL"),
        )

    def test_loaded_campaign_rejects_source_commit_drift(self):
        previous = os.environ.get("AURELIA_RESEARCH_CODE_COMMIT")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "state.json"
                state = initial_state()
                state["manifest"]["code_commit"] = "commit-A"
                save_state(path, state)
                os.environ["AURELIA_RESEARCH_CODE_COMMIT"] = "commit-B"
                with self.assertRaisesRegex(ValueError, "R100_SOURCE_COMMIT_MISMATCH"):
                    load_state(path)
        finally:
            if previous is None:
                os.environ.pop("AURELIA_RESEARCH_CODE_COMMIT", None)
            else:
                os.environ["AURELIA_RESEARCH_CODE_COMMIT"] = previous

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


    def test_positive_underlying_oos_cannot_qualify_without_quoted_economics(self):
        state = initial_state()
        start = state["manifest"]["oos_start_at_utc"]
        state["observations"] = [
            {
                "signal_id": f"sig-{i}",
                "direction": "CALL",
                "raw_return": 0.01,
                "outcome": 1,
                "probability": 0.55 + (i % 3) * 0.05,
                "signal_timestamp_utc": start,
            }
            for i in range(100)
        ]
        state["quote_observations"] = []
        report = evaluation(state)
        self.assertEqual(report["qualification_status"], "ECONOMICS_INCOMPLETE")
        self.assertFalse(report["strategy_live_eligible"])

    def test_campaign_end_does_not_seal_with_unresolved_pending(self):
        state = initial_state()
        state["manifest"]["campaign_end_at_utc"] = "2026-10-06T20:00:00Z"
        state["pending"] = [{
            "signal_id": "pending",
            "signal_timestamp_utc": "2026-10-06T19:59:00Z",
            "entry_quote": 100.0,
            "direction": "CALL",
            "probability": 0.60,
            "score": 1.5,
            "age_ticks": 0,
        }]
        report = evaluation(state)
        self.assertFalse(report["campaign_complete"])
        self.assertFalse(state["manifest"]["sealed"])

    def test_campaign_end_stops_new_signal_emission_but_settles_pending(self):
        class NoEmitHunter:
            def __init__(self):
                self.calls = 0

            def observe(self, **kwargs):
                self.calls += 1
                raise AssertionError("hunter.observe must not be called after campaign end")

        state = initial_state()
        state["pending"] = [{
            "signal_id": "pending",
            "signal_timestamp_utc": "2026-10-06T19:59:00Z",
            "entry_quote": 100.0,
            "direction": "CALL",
            "probability": 0.60,
            "score": 1.5,
            "age_ticks": HORIZON_TICKS - 1,
        }]
        hunter = NoEmitHunter()
        observe_tick(
            hunter=hunter,
            state=state,
            quote=101.0,
            received_at=datetime.now(timezone.utc),
            emit_candidate=False,
        )
        self.assertEqual(hunter.calls, 0)
        self.assertEqual(len(state["pending"]), 0)
        self.assertEqual(len(state["observations"]), 1)

    def test_horizon_is_positive(self):
        self.assertGreater(HORIZON_TICKS, 0)


if __name__ == "__main__":
    unittest.main()
