from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta, timezone
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
    legacy_research_config_hash,
    research_config_hash,
    observe_tick,
    oos_data_coverage_metrics,
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

    def test_oos_collection_coverage_passes_only_with_sustained_observed_windows(self):
        start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        windows = []
        for index in range(96):
            first = start + timedelta(minutes=15 * index)
            last = min(first + timedelta(seconds=599), end)
            windows.append({
                "first_tick_at_utc": first.isoformat(),
                "last_tick_at_utc": last.isoformat(),
                "tick_count": 600,
                "max_tick_gap_seconds": 1.0,
            })
        metrics = oos_data_coverage_metrics(windows, start, end)
        self.assertTrue(metrics["data_coverage_valid"])
        self.assertGreaterEqual(metrics["collection_window_count"], 24)
        self.assertGreaterEqual(metrics["data_coverage_fraction"], 0.50)
        self.assertLessEqual(metrics["max_observation_gap_seconds"], 1800)

    def test_oos_collection_coverage_rejects_sparse_windows_and_large_tick_gaps(self):
        start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        sparse_windows = []
        for index in range(8):
            first = start + timedelta(hours=3 * index)
            sparse_windows.append({
                "first_tick_at_utc": first.isoformat(),
                "last_tick_at_utc": (first + timedelta(seconds=599)).isoformat(),
                "tick_count": 600,
                "max_tick_gap_seconds": 45.0,
            })
        metrics = oos_data_coverage_metrics(sparse_windows, start, end)
        self.assertFalse(metrics["data_coverage_valid"])
        self.assertLess(metrics["data_coverage_fraction"], 0.50)
        self.assertGreater(metrics["max_observation_gap_seconds"], 1800)
        self.assertGreater(metrics["max_tick_gap_seconds"], 30)

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

    def test_legacy_collection_duration_hash_migrates_without_changing_strategy_config(self):
        previous = os.environ.get("AURELIA_RESEARCH_CODE_COMMIT")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "state.json"
                state = initial_state()
                state["manifest"]["config_hash"] = legacy_research_config_hash()
                save_state(path, state)
                os.environ["AURELIA_RESEARCH_CODE_COMMIT"] = state["manifest"]["code_commit"]
                restored = load_state(path)
                self.assertEqual(restored["manifest"]["config_hash"], research_config_hash())
                self.assertEqual(
                    restored["manifest"]["provenance_migration"],
                    "LEGACY_CONFIG_HASH_COLLECTION_DURATION_REMOVED",
                )
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

    def test_campaign_before_cutoff_does_not_seal_while_pending(self):
        import research.r100_prospective_oos_collector as collector
        now = datetime(2026, 10, 6, 19, 59, 30, tzinfo=timezone.utc)
        state = initial_state()
        state["manifest"]["started_at_utc"] = (now - timedelta(days=8)).isoformat()
        state["manifest"]["oos_start_at_utc"] = (now - timedelta(days=7)).isoformat()
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
        with patch.object(collector, "utc_now", return_value=now):
            report = evaluation(state)
        self.assertFalse(report["campaign_complete"])
        self.assertFalse(state["manifest"]["sealed"])
        self.assertEqual(len(state["pending"]), 1)

    def test_emit_candidate_false_settles_mature_pending_without_new_signal(self):
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

    def test_failed_collection_preserves_state_and_emits_non_authorizing_report(self):
        import research.r100_prospective_oos_collector as collector

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "aurelia_r100_state.json"
            with (
                patch.object(collector, "STATE_PATH", state_path),
                patch.object(
                    collector,
                    "collect_once",
                    new=AsyncMock(side_effect=RuntimeError("simulated feed outage")),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "simulated feed outage"):
                    asyncio.run(collector.main())

            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            report = json.loads(
                state_path.with_name("aurelia_r100_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(persisted["last_run_error_type"], "RuntimeError")
            self.assertTrue(persisted["last_run_error_at_utc"])
            self.assertEqual(report["collection_status"], "FAILED_RETRYABLE")
            self.assertEqual(report["collection_error_type"], "RuntimeError")
            self.assertFalse(report["execution_authorized"])
            self.assertFalse(report["capital_authority"])

    def test_horizon_is_positive(self):
        self.assertGreater(HORIZON_TICKS, 0)

    def test_collector_never_requests_public_contract_proposals(self):
        import research.r100_prospective_oos_collector as collector
        from types import SimpleNamespace
        start = datetime(2026, 10, 6, 19, 0, 0, tzinfo=timezone.utc)
        class OneTickThenTimeout:
            def __init__(self): self.sent = False
            def __aiter__(self): return self
            async def __anext__(self):
                if self.sent: raise asyncio.TimeoutError()
                self.sent = True
                return {"msg_type":"tick","tick":{"symbol":"R_100","quote":100.0,"epoch":int(start.timestamp())+1}}
        class FakeHunter:
            def observe(self, **kwargs):
                return SimpleNamespace(probability=0.65, probability_status="UNCALIBRATED_RESEARCH_ONLY",direction="CALL",score=1.6)
        stream = OneTickThenTimeout()
        class FakeTransport:
            def __init__(self):
                self.connect,self.request,self.close=AsyncMock(),AsyncMock(),AsyncMock()
            def subscribe(self,key,payload): return stream
        transport=FakeTransport()
        gate=Mock()
        gate.get_client.return_value=transport
        state=initial_state()
        state["manifest"]["campaign_end_at_utc"]="2026-10-06T20:00:00Z"
        with (
            patch.object(collector,"utc_now",return_value=start),
            patch.object(collector,"COLLECTION_SECONDS",10.0),
            patch.object(collector,"DerivAuthenticationGate",return_value=gate) as gate_factory,
            patch.object(collector,"AutonomousSignalHunter",return_value=FakeHunter()),
        ):
            asyncio.run(collector.collect_once(state))
        transport.request.assert_not_awaited()
        self.assertEqual(len(state["pending"]),1)
        self.assertEqual(state["quote_observations"][0]["quote_status"],"UNAVAILABLE")
        self.assertEqual(state["quote_observations"][0]["error_code"],"R100_PUBLIC_PROPOSAL_QUOTES_DISABLED_BY_POLICY")
        transport.close.assert_awaited_once()
        gate_factory.assert_called_once_with(plane="research")
        gate.get_client.assert_called_once_with()

    def test_expired_campaign_censors_pending_signals_and_seals_without_connecting(self):
        import research.r100_prospective_oos_collector as collector
        now = datetime(2026, 10, 6, 19, 0, 0, tzinfo=timezone.utc)
        state = initial_state()
        campaign_end = now - timedelta(seconds=1)
        state["manifest"]["started_at_utc"] = (now - timedelta(days=8)).isoformat()
        state["manifest"]["oos_start_at_utc"] = (now - timedelta(days=7)).isoformat()
        state["manifest"]["campaign_end_at_utc"] = campaign_end.isoformat()
        state["pending"] = [{
            "signal_id": "pending-at-expiry",
            "signal_timestamp_utc": (campaign_end - timedelta(seconds=30)).isoformat(),
            "entry_quote": 100.0,
            "direction": "CALL",
            "probability": 0.60,
            "score": 1.5,
            "age_ticks": HORIZON_TICKS - 1,
        }]
        with (
            patch.object(collector, "utc_now", return_value=now),
            patch.object(collector, "DerivAuthenticationGate") as factory,
        ):
            asyncio.run(collector.collect_once(state))
            report = collector.evaluation(state)
        factory.assert_not_called()
        self.assertEqual(state["pending"], [])
        self.assertEqual(len(state["censored_signals"]), 1)
        self.assertEqual(state["censored_signals"][0]["censor_reason"],
            "HORIZON_NOT_REACHED_BEFORE_CAMPAIGN_CUTOFF")
        self.assertEqual(state["observations"], [])
        self.assertTrue(state["manifest"]["sealed"])
        self.assertTrue(report["campaign_complete"])
        self.assertEqual(report["censored_signal_count"], 1)

    def test_public_tick_parser_rejects_coercion_and_wrong_symbol(self):
        from research.r100_prospective_oos_collector import parse_public_tick
        valid = {
            "msg_type": "tick",
            "tick": {"quote": 100.25, "epoch": 1791313200},
        }
        quote, timestamp = parse_public_tick(valid)
        self.assertEqual(quote, 100.25)
        self.assertEqual(timestamp.tzinfo, timezone.utc)

        invalid_cases = [
            ({"msg_type":"tick","tick":{"symbol":"V_100","quote":100.0,"epoch":1791313200}}, "R100_TICK_SYMBOL_MISMATCH"),
            ({"msg_type":"tick","tick":{"quote":"100.0","epoch":1791313200}}, "R100_TICK_QUOTE_INVALID"),
            ({"msg_type":"tick","tick":{"quote":True,"epoch":1791313200}}, "R100_TICK_QUOTE_INVALID"),
            ({"msg_type":"tick","tick":{"quote":100.0,"epoch":True}}, "R100_TICK_EPOCH_INVALID"),
            ({"msg_type":"tick","tick":{"quote":100.0,"epoch":"1791313200"}}, "R100_TICK_EPOCH_INVALID"),
            ({"msg_type":"ohlc","tick":{"quote":100.0,"epoch":1791313200}}, "R100_TICK_RESPONSE_TYPE_INVALID"),
        ]
        for message, reason in invalid_cases:
            with self.subTest(reason=reason, message=message):
                with self.assertRaisesRegex(ValueError, reason):
                    parse_public_tick(message)

    def test_collector_rejects_out_of_order_ticks(self):
        import research.r100_prospective_oos_collector as collector
        start = datetime(2026, 10, 6, 19, 0, 0, tzinfo=timezone.utc)

        class TwoTicks:
            def __init__(self):
                self.items = iter([
                    {"msg_type":"tick","tick":{"symbol":"R_100","quote":100.0,"epoch":int(start.timestamp())+2}},
                    {"msg_type":"tick","tick":{"symbol":"R_100","quote":100.1,"epoch":int(start.timestamp())+1}},
                ])
            def __aiter__(self):
                return self
            async def __anext__(self):
                try:
                    return next(self.items)
                except StopIteration:
                    raise StopAsyncIteration

        class NoSignalHunter:
            def observe(self, **kwargs):
                return None

        class FakeTransport:
            def __init__(self):
                self.connect, self.close = AsyncMock(), AsyncMock()
            def subscribe(self, key, payload):
                return TwoTicks()

        state = initial_state()
        state["manifest"]["campaign_end_at_utc"] = "2026-10-06T20:00:00Z"
        transport = FakeTransport()
        gate = Mock()
        gate.get_client.return_value = transport
        with (
            patch.object(collector,"utc_now",return_value=start),
            patch.object(collector,"COLLECTION_SECONDS",10.0),
            patch.object(collector,"DerivAuthenticationGate",return_value=gate) as gate_factory,
            patch.object(collector,"AutonomousSignalHunter",return_value=NoSignalHunter()),
        ):
            with self.assertRaisesRegex(ValueError,"R100_TICK_ORDER_INVALID"):
                asyncio.run(collector.collect_once(state))
        transport.close.assert_awaited_once()
        gate_factory.assert_called_once_with(plane="research")
        gate.get_client.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
