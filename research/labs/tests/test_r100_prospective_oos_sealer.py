from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.r100_prospective_oos_collector import initial_state, save_state
from research.r100_prospective_oos_sealer import seal_expired_campaign


class R100ProspectiveSealerTest(unittest.TestCase):
    def test_expired_campaign_is_sealed_offline_and_pending_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aurelia_r100_state.json"
            state = initial_state()
            state["manifest"]["campaign_end_at_utc"] = "2026-10-06T20:00:00Z"
            pending = {
                "signal_id": "pending-1",
                "signal_timestamp_utc": "2026-10-06T19:59:00Z",
                "entry_quote": 100.0,
                "direction": "CALL",
                "probability": 0.60,
                "score": 1.5,
                "age_ticks": 0,
            }
            state["pending"] = [pending]
            save_state(path, state)
            report_path = path.with_name("aurelia_r100_report.json")
            report_path.write_text(json.dumps({
                "qualification_status": "LAST_CAPTURED_SNAPSHOT",
                "oos_mean_strategy_return": 0.123,
                "execution_authorized": False,
                "capital_authority": False,
            }))
            result = seal_expired_campaign(
                path,
                now=datetime(2026, 10, 7, tzinfo=timezone.utc),
            )
            persisted = json.loads(path.read_text(encoding="utf-8"))
            report = json.loads(path.with_name("aurelia_r100_report.json").read_text())
            self.assertEqual(result["status"], "SEALED_WITH_UNRESOLVED_PENDING")
            self.assertTrue(persisted["manifest"]["sealed"])
            self.assertEqual(persisted["pending"], [pending])
            self.assertEqual(report["pending_resolution_status"], "UNRESOLVED_NO_BACKFILL")
            self.assertEqual(report["pending_count"], 1)
            self.assertFalse(report["execution_authorized"])
            self.assertFalse(report["capital_authority"])
            self.assertEqual(report["last_collection_qualification_status"], "LAST_CAPTURED_SNAPSHOT")
            self.assertEqual(report["qualification_status"], "NOT_RECALCULATED_AFTER_EXPIRY")
            self.assertEqual(report["oos_mean_strategy_return"], 0.123)
            self.assertEqual(report["evaluation_snapshot_status"], "LAST_COLLECTION_SNAPSHOT_PRESERVED")

    def test_active_campaign_is_not_sealed_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "aurelia_r100_state.json"
            state = initial_state()
            state["manifest"]["campaign_end_at_utc"] = "2026-10-08T20:00:00Z"
            save_state(path, state)
            result = seal_expired_campaign(
                path,
                now=datetime(2026, 10, 7, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "NOT_DUE")
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(persisted["manifest"]["sealed"])


if __name__ == "__main__":
    unittest.main()
