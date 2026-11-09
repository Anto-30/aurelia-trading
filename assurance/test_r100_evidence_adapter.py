import datetime
import json
import unittest

import assurance.evidence_writer
import assurance.r100_evidence_adapter


def _iso(value):
    return value.isoformat().replace("+00:00", "Z")


def _fixture():
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    started = now - datetime.timedelta(days=8)
    oos_start = started + datetime.timedelta(days=1)
    campaign_end = now - datetime.timedelta(minutes=5)
    source_commit = "a" * 40
    config_hash = "b" * 64
    observations = []
    group_probabilities = [0.56, 0.66, 0.71]
    group_outcomes = [22, 26, 28]
    counts = [0, 0, 0]
    for index in range(120):
        group = index % 3
        cycle = counts[group]
        outcome = int(cycle < group_outcomes[group])
        counts[group] += 1
        signal_time = oos_start + datetime.timedelta(seconds=index * 30)
        observations.append({
            "strategy_id": "R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0",
            "strategy_version": "0.2.0",
            "symbol": "R_100",
            "regime": "ALL_MARKET",
            "signal_timestamp_utc": _iso(signal_time),
            "exit_timestamp_utc": _iso(signal_time + datetime.timedelta(seconds=10)),
            "probability": group_probabilities[group],
            "outcome": outcome,
            "raw_return": 0.002 if outcome else -0.001,
            "direction": "CALL",
        })
    manifest = {
        "experiment_id": "R100-TEST-SEALED",
        "strategy_id": "R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0",
        "strategy_version": "0.2.0",
        "code_commit": source_commit,
        "producer": {
            "workflow_path": ".github/workflows/r100-prospective-oos.yml",
            "workflow_id": "1234",
            "workflow_run_id": "5678",
            "event": "schedule",
            "head_branch": "main",
            "head_sha": source_commit,
        },
        "config_hash": config_hash,
        "started_at_utc": _iso(started),
        "oos_start_at_utc": _iso(oos_start),
        "campaign_end_at_utc": _iso(campaign_end),
        "trial_count": 1,
        "search_degrees_of_freedom": 0,
        "oos_reuse_count": 0,
        "sealed": True,
    }
    data_windows = []
    cursor = oos_start
    while cursor < campaign_end:
        first_tick = cursor
        # campaign_end is an exclusive cutoff; the final observed tick
        # must be strictly earlier than it.
        last_tick = min(
            cursor + datetime.timedelta(seconds=599),
            campaign_end - datetime.timedelta(seconds=1),
        )
        if last_tick > first_tick:
            data_windows.append({
                "run_started_at_utc": _iso(first_tick),
                "run_completed_at_utc": _iso(last_tick),
                "first_tick_at_utc": _iso(first_tick),
                "last_tick_at_utc": _iso(last_tick),
                "tick_count": 600,
                "max_tick_gap_seconds": 1.0,
                "actual_collection_seconds": 600.0,
            })
        cursor += datetime.timedelta(seconds=900)
    manifest["data_windows"] = data_windows
    state = {
        "schema": "aurelia.r100.prospective_oos.v1",
        "manifest": manifest,
        "observations": observations,
        "pending": [],
        "censored_signals": [],
        "quote_observations": [],
        "last_run_completed_at_utc": _iso(now - datetime.timedelta(minutes=1)),
    }
    calibration = assurance.r100_evidence_adapter._recompute_probability_metrics(observations)
    mean_return = sum(
        row["raw_return"] if row["direction"] == "CALL" else -row["raw_return"]
        for row in observations
    ) / len(observations)
    archive_hash = assurance.r100_evidence_adapter._canonical_hash({
        "manifest": manifest,
        "observations": observations,
        "quote_observations": [],
        "censored_signals": [],
    })
    coverage = assurance.r100_evidence_adapter._recompute_data_coverage(
        data_windows, oos_start, campaign_end
    )
    report = {
        "schema": "aurelia.r100.prospective_oos.report.v1",
        "data_coverage": coverage,
        "data_coverage_valid": coverage["data_coverage_valid"],
        "data_coverage_fraction": coverage["data_coverage_fraction"],
        "max_observation_gap_seconds": coverage["max_observation_gap_seconds"],
        "collection_window_count": coverage["collection_window_count"],
        "collection_status": "PASS",
        "campaign_complete": True,
        "retuning_after_seal": False,
        "archive_hash": archive_hash,
        "strategy_version": "0.2.0",
        "oos_observations": len(observations),
        "observations_total": len(observations),
        "censored_signal_count": len(state.get("censored_signals", [])),
        "oos_mean_strategy_return": mean_return,
        "multiple_testing": {
            "status": "ACCOUNTED",
            "trial_count": 1,
            "search_degrees_of_freedom": 0,
            "oos_reuse_count": 0,
        },
        "probability": calibration,
    }
    state_bytes = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    report_bytes = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    return state, report, state_bytes, report_bytes


class R100EvidenceAdapterTest(unittest.TestCase):
    def test_sealed_oos_and_calibration_generate_provenance_bound_records(self):
        state, report, state_bytes, report_bytes = _fixture()
        records = assurance.r100_evidence_adapter.adapt_sealed_campaign(
            state, report, state_bytes=state_bytes, report_bytes=report_bytes
        )
        self.assertEqual(set(records), {"prospective_oos.json", "calibration.json"})
        for record in records.values():
            self.assertEqual(record["provenance"]["source_commit"], "a" * 40)
            self.assertFalse(record["capital_authority_granted"])
            self.assertEqual(record["orders_submitted"], 0)
            self.assertFalse(record["execution_authorized"])
            self.assertFalse(record["live_execution"])
            unsigned = {key: value for key, value in record.items() if key != "record_hash"}
            self.assertEqual(
                record["record_hash"],
                assurance.evidence_writer.payload_sha256(unsigned),
            )

    def test_valid_oos_with_uncalibrated_probabilities_is_partial_evidence(self):
        state, report, state_bytes, report_bytes = _fixture()
        for row in state["observations"]:
            row["outcome"] = 1
            row["raw_return"] = 0.002
        report["oos_mean_strategy_return"] = 0.002
        report["probability"] = assurance.r100_evidence_adapter._recompute_probability_metrics(
            state["observations"]
        )
        report["archive_hash"] = assurance.r100_evidence_adapter._canonical_hash({
            "manifest": state["manifest"],
            "observations": state["observations"],
            "quote_observations": [],
            "censored_signals": state.get("censored_signals", []),
        })
        state_bytes = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
        report_bytes = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
        records = assurance.r100_evidence_adapter.adapt_sealed_campaign(
            state, report, state_bytes=state_bytes, report_bytes=report_bytes
        )
        self.assertEqual(set(records), {"prospective_oos.json"})

    def test_unsealed_campaign_is_rejected(self):
        state, report, state_bytes, report_bytes = _fixture()
        state["manifest"]["sealed"] = False
        with self.assertRaisesRegex(ValueError, "R100_CAMPAIGN_NOT_SEALED"):
            assurance.r100_evidence_adapter.adapt_sealed_campaign(
                state, report, state_bytes=state_bytes, report_bytes=report_bytes
            )

    def test_archive_hash_mismatch_is_rejected(self):
        state, report, state_bytes, report_bytes = _fixture()
        report["archive_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "R100_ARCHIVE_HASH_MISMATCH"):
            assurance.r100_evidence_adapter.adapt_sealed_campaign(
                state, report, state_bytes=state_bytes, report_bytes=report_bytes
            )

    def test_low_sample_campaign_is_rejected(self):
        state, report, state_bytes, report_bytes = _fixture()
        state["observations"] = state["observations"][:90]
        report["observations_total"] = 90
        report["oos_observations"] = 90
        report["archive_hash"] = assurance.r100_evidence_adapter._canonical_hash({
            "manifest": state["manifest"],
            "observations": state["observations"],
            "quote_observations": [],
            "censored_signals": state.get("censored_signals", []),
        })
        with self.assertRaisesRegex(ValueError, "R100_OOS_SAMPLE_LT_100"):
            assurance.r100_evidence_adapter.adapt_sealed_campaign(
                state, report,
                state_bytes=json.dumps(state, sort_keys=True, separators=(",", ":")).encode(),
                report_bytes=report_bytes
            )

    def _refresh_hashes(self, state, report):
        report["archive_hash"] = assurance.r100_evidence_adapter._canonical_hash({
            "manifest": state["manifest"], "observations": state["observations"],
            "quote_observations": state["quote_observations"],
            "censored_signals": state.get("censored_signals", []),
        })
        return (
            json.dumps(state, sort_keys=True, separators=(",", ":")).encode(),
            json.dumps(report, sort_keys=True, separators=(",", ":")).encode(),
        )

    def test_post_expiry_exit_is_rejected(self):
        state, report, _, _ = _fixture()
        state["observations"][0]["exit_timestamp_utc"] = state["manifest"]["campaign_end_at_utc"]
        sb, rb = self._refresh_hashes(state, report)
        with self.assertRaisesRegex(ValueError, "R100_POST_EXPIRY_DATA_PRESENT"):
            assurance.r100_evidence_adapter.adapt_sealed_campaign(state, report, state_bytes=sb, report_bytes=rb)

    def test_post_expiry_signal_is_rejected(self):
        state, report, _, _ = _fixture()
        state["observations"][0]["signal_timestamp_utc"] = state["manifest"]["campaign_end_at_utc"]
        state["observations"][0]["exit_timestamp_utc"] = state["manifest"]["campaign_end_at_utc"]
        sb, rb = self._refresh_hashes(state, report)
        with self.assertRaisesRegex(ValueError, "R100_POST_EXPIRY_DATA_PRESENT"):
            assurance.r100_evidence_adapter.adapt_sealed_campaign(state, report, state_bytes=sb, report_bytes=rb)

    def test_post_expiry_quote_is_rejected(self):
        state, report, _, _ = _fixture()
        state["quote_observations"] = [{"signal_id":"late","captured_at_utc":state["manifest"]["campaign_end_at_utc"],"quote_status":"UNAVAILABLE"}]
        sb, rb = self._refresh_hashes(state, report)
        with self.assertRaisesRegex(ValueError, "R100_POST_EXPIRY_DATA_PRESENT"):
            assurance.r100_evidence_adapter.adapt_sealed_campaign(state, report, state_bytes=sb, report_bytes=rb)

    def test_outcome_boolean_and_coercions_are_rejected(self):
        for invalid in (True, 1.0, "1"):
            state, report, _, _ = _fixture()
            state["observations"][0]["outcome"] = invalid
            sb, rb = self._refresh_hashes(state, report)
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "R100_EVIDENCE_OUTCOME_INVALID"):
                    assurance.r100_evidence_adapter.adapt_sealed_campaign(state, report, state_bytes=sb, report_bytes=rb)

    def test_strategy_cell_mismatch_is_rejected(self):
        for key, value in (("strategy_id","OTHER"),("symbol","V_100"),("regime","TREND")):
            state, report, _, _ = _fixture()
            state["observations"][0][key] = value
            sb, rb = self._refresh_hashes(state, report)
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "R100_OBSERVATION_STRATEGY_CELL_MISMATCH"):
                    assurance.r100_evidence_adapter.adapt_sealed_campaign(state, report, state_bytes=sb, report_bytes=rb)

    def test_malformed_window_count_is_rejected(self):
        state, report, _, _ = _fixture()
        state["manifest"]["data_windows"][0]["tick_count"] = 1.5
        sb, rb = self._refresh_hashes(state, report)
        with self.assertRaisesRegex(ValueError, "R100_DATA_WINDOW_TICK_COUNT_INVALID"):
            assurance.r100_evidence_adapter.adapt_sealed_campaign(state, report, state_bytes=sb, report_bytes=rb)

    def test_untrusted_campaign_producer_is_rejected(self):
        state, report, _, _ = _fixture()
        state["manifest"]["producer"]["head_branch"] = "feature/untrusted"
        sb, rb = self._refresh_hashes(state, report)
        with self.assertRaisesRegex(ValueError, "R100_CAMPAIGN_PRODUCER_INVALID"):
            assurance.r100_evidence_adapter.adapt_sealed_campaign(state, report, state_bytes=sb, report_bytes=rb)


    def test_censored_signal_is_retained_but_never_counted_as_oos_return(self):
        state, report, _, _ = _fixture()
        row = state["observations"][0]
        state["censored_signals"] = [{
            "signal_id": "censored-only",
            "strategy_id": "R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0",
            "strategy_version": "0.2.0",
            "symbol": "R_100",
            "regime": "ALL_MARKET",
            "signal_timestamp_utc": row["signal_timestamp_utc"],
            "censored_at_utc": state["manifest"]["campaign_end_at_utc"],
            "censor_reason": "HORIZON_NOT_REACHED_BEFORE_CAMPAIGN_CUTOFF",
            "direction": "CALL",
            "probability": 0.60,
            "score": 1.5,
            "horizon_ticks": 10,
            "age_ticks": 9,
        }]
        report["censored_signal_count"] = 1
        sb, rb = self._refresh_hashes(state, report)
        records = assurance.r100_evidence_adapter.adapt_sealed_campaign(
            state, report, state_bytes=sb, report_bytes=rb
        )
        self.assertEqual(records["prospective_oos.json"]["censored_signal_count"], 1)
        self.assertEqual(records["prospective_oos.json"]["min_trades_per_strategy_symbol_regime"], 120)

    def test_multiple_ticks_in_one_epoch_second_do_not_create_fake_coverage(self):
        tick_time = datetime.datetime(2026, 10, 6, 19, 0, 0, tzinfo=datetime.timezone.utc)
        result = assurance.r100_evidence_adapter._recompute_data_coverage(
            [{
                "run_started_at_utc": _iso(tick_time - datetime.timedelta(seconds=1)),
                "run_completed_at_utc": _iso(tick_time + datetime.timedelta(seconds=1)),
                "first_tick_at_utc": _iso(tick_time),
                "last_tick_at_utc": _iso(tick_time),
                "tick_count": 3,
                "max_tick_gap_seconds": 0,
            }],
            tick_time - datetime.timedelta(minutes=1),
            tick_time + datetime.timedelta(minutes=1),
        )
        self.assertEqual(result["collection_window_count"], 0)
        self.assertEqual(result["data_coverage_fraction"], 0.0)
        self.assertFalse(result["data_coverage_valid"])


if __name__ == "__main__":
    unittest.main()
