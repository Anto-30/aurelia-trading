from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.r100_prospective_oos_collector import initial_state, save_state
from research.r100_prospective_oos_sealer import seal_expired_campaign


def _collection_hashes(state):
    common = {
        "manifest": state["manifest"],
        "observations": state.get("observations", []),
        "quote_observations": state.get("quote_observations", []),
    }
    payloads = [
        {**common, "censored_signals": state.get("censored_signals", [])},
        {**common, "pending": state.get("pending", [])},
        common,
    ]
    return [
        hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        for payload in payloads
    ]


class R100ProspectiveSealerTest(unittest.TestCase):
    def _save(self, path, state, report=None):
        save_state(path, state)
        report_path = path.with_name("aurelia_r100_report.json")
        if report is not None:
            report_path.write_text(
                json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False),
                encoding="utf-8",
            )
        return report_path

    def test_expired_campaign_preserves_pending_and_last_metrics_without_rescoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aurelia_r100_state.json"
            state = initial_state()
            state["manifest"]["campaign_end_at_utc"] = "2026-10-06T20:00:00Z"
            state["observations"] = [{
                "signal_timestamp_utc": "2026-10-06T19:58:00Z",
                "exit_timestamp_utc": "2026-10-06T19:59:00Z",
            }]
            pending = {
                "signal_id": "pending-1",
                "signal_timestamp_utc": "2026-10-06T19:59:00Z",
                "entry_quote": 100.0,
                "direction": "CALL",
                "probability": 0.60,
                "score": 1.5,
                "age_ticks": 9,
            }
            state["pending"] = [pending]
            report = {
                "qualification_status": "LAST_CAPTURED_SNAPSHOT",
                "oos_mean_strategy_return": 0.123,
                "execution_authorized": False,
                "capital_authority": False,
                "campaign_complete": False,
                "archive_hash": _collection_hashes(state)[0],
            }
            report_path = self._save(path, state, report)
            result = seal_expired_campaign(
                path,
                now=datetime(2026, 10, 7, tzinfo=timezone.utc),
            )
            persisted = json.loads(path.read_text(encoding="utf-8"))
            sealed_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "SEALED_WITH_UNRESOLVED_PENDING")
            self.assertTrue(persisted["manifest"]["sealed"])
            self.assertEqual(persisted["pending"], [pending])
            self.assertEqual(sealed_report["pending_resolution_status"], "UNRESOLVED_NO_BACKFILL")
            self.assertEqual(sealed_report["pending_count"], 1)
            self.assertFalse(sealed_report["execution_authorized"])
            self.assertFalse(sealed_report["capital_authority"])
            self.assertEqual(sealed_report["last_collection_qualification_status"], "LAST_CAPTURED_SNAPSHOT")
            self.assertEqual(sealed_report["qualification_status"], "NOT_RECALCULATED_AFTER_EXPIRY")
            self.assertEqual(sealed_report["oos_mean_strategy_return"], 0.123)
            self.assertEqual(sealed_report["evaluation_snapshot_status"], "LAST_COLLECTION_SNAPSHOT_PRESERVED")
            self.assertEqual(sealed_report["preseal_archive_integrity"], "VERIFIED")
            self.assertEqual(sealed_report["archive_hash"], result["archive_hash"])

    def test_post_expiry_exit_is_rejected_without_mutating_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aurelia_r100_state.json"
            state = initial_state()
            state["manifest"]["campaign_end_at_utc"] = "2026-10-06T20:00:00Z"
            state["observations"] = [{
                "signal_timestamp_utc": "2026-10-06T19:59:00Z",
                "exit_timestamp_utc": "2026-10-06T20:00:01Z",
            }]
            self._save(path, state)
            original = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "R100_POST_EXPIRY_DATA_PRESENT"):
                seal_expired_campaign(path, now=datetime(2026, 10, 7, tzinfo=timezone.utc))
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(path.with_name("aurelia_r100_report.json").exists())

    def test_post_expiry_quote_is_rejected_without_mutating_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aurelia_r100_state.json"
            state = initial_state()
            state["manifest"]["campaign_end_at_utc"] = "2026-10-06T20:00:00Z"
            state["quote_observations"] = [{
                "signal_id": "quote-after-cutoff",
                "captured_at_utc": "2026-10-06T20:00:00Z",
                "quote_status": "UNAVAILABLE",
            }]
            self._save(path, state)
            original = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "R100_POST_EXPIRY_DATA_PRESENT"):
                seal_expired_campaign(path, now=datetime(2026, 10, 7, tzinfo=timezone.utc))
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(path.with_name("aurelia_r100_report.json").exists())

    def test_post_expiry_censored_signal_is_rejected_without_mutating_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aurelia_r100_state.json"
            state = initial_state()
            state["manifest"]["campaign_end_at_utc"] = "2026-10-06T20:00:00Z"
            state["censored_signals"] = [{
                "signal_id": "late-censored",
                "signal_timestamp_utc": "2026-10-06T20:00:00Z",
            }]
            self._save(path, state)
            original = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "R100_POST_EXPIRY_DATA_PRESENT"):
                seal_expired_campaign(path, now=datetime(2026, 10, 7, tzinfo=timezone.utc))
            self.assertEqual(path.read_bytes(), original)

    def test_preseal_archive_hash_mismatch_blocks_sealing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aurelia_r100_state.json"
            state = initial_state()
            state["manifest"]["campaign_end_at_utc"] = "2026-10-06T20:00:00Z"
            report_path = self._save(path, state, {"archive_hash": "0" * 64})
            original = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "R100_PRESEAL_ARCHIVE_HASH_MISMATCH"):
                seal_expired_campaign(path, now=datetime(2026, 10, 7, tzinfo=timezone.utc))
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(report_path.read_text(encoding="utf-8"), json.dumps({"archive_hash": "0" * 64}, sort_keys=True, separators=(",", ":"), allow_nan=False))

    def test_active_campaign_is_not_sealed_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aurelia_r100_state.json"
            state = initial_state()
            state["manifest"]["campaign_end_at_utc"] = "2026-10-08T20:00:00Z"
            self._save(path, state)
            result = seal_expired_campaign(path, now=datetime(2026, 10, 7, tzinfo=timezone.utc))
            self.assertEqual(result["status"], "NOT_DUE")
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(persisted["manifest"]["sealed"])


    def test_legacy_pending_archive_hash_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aurelia_r100_state.json"
            state = initial_state()
            state["manifest"]["campaign_end_at_utc"] = "2026-10-06T20:00:00Z"
            pending = [{
                "signal_id": "legacy-pending",
                "signal_timestamp_utc": "2026-10-06T19:59:00Z",
                "entry_quote": 100.0,
                "direction": "CALL",
                "probability": 0.60,
                "score": 1.2,
                "age_ticks": 2,
            }]
            state["pending"] = pending
            common = {
                "manifest": state["manifest"],
                "observations": state.get("observations", []),
                "quote_observations": state.get("quote_observations", []),
            }
            old_hash = hashlib.sha256(
                json.dumps(
                    {**common, "pending": pending},
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            report_path = self._save(path, state, {
                "archive_hash": old_hash,
                "qualification_status": "LAST_CAPTURED",
            })
            result = seal_expired_campaign(
                path,
                now=datetime(2026, 10, 7, tzinfo=timezone.utc),
            )
            sealed_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "SEALED_WITH_UNRESOLVED_PENDING")
            self.assertEqual(
                sealed_report["preseal_archive_integrity"],
                "VERIFIED_SUPPORTED_HASH_SCHEMA",
            )
            self.assertEqual(
                sealed_report["pending_resolution_status"],
                "UNRESOLVED_NO_BACKFILL",
            )


if __name__ == "__main__":
    unittest.main()
