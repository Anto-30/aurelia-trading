"""Tests for evidence-only nightly paper review reports."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.paper_agent.ledger import PaperEventLedger
from research.paper_agent.report import (
    build_nightly_report, read_events_readonly, schema_diff, write_report_atomic,
)


class NightlyReportTests(unittest.TestCase):
    def test_report_never_fabricates_pnl_or_calibration(self):
        now = datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc)
        events = [
            {
                "sequence": 1, "event_id": "intent-1", "event_type": "PAPER_INTENT",
                "occurred_at_utc": (now - timedelta(minutes=10)).isoformat(),
                "payload_json": json.dumps({
                    "decision": {"regime": "trending", "confidence": 0.72},
                    "allowed_by_risk_gate": True,
                }),
            },
            {
                "sequence": 2, "event_id": "miss-1", "event_type": "MISSED_SIGNAL",
                "occurred_at_utc": (now - timedelta(minutes=5)).isoformat(),
                "payload_json": json.dumps({"reason": "LOW_CONFIDENCE"}),
            },
        ]
        report = build_nightly_report(events, generated_at_utc=now)
        self.assertEqual(report["event_counts_24h"]["PAPER_INTENT"], 1)
        self.assertEqual(report["event_counts_24h"]["MISSED_SIGNAL"], 1)
        self.assertIsNone(report["simulated_pnl"])
        self.assertIsNone(report["brier_score"])
        self.assertEqual(report["calibration_status"], "NOT_MEASURABLE_WITHOUT_VERIFIED_OUTCOME_LABELS")
        self.assertTrue(report["paper_intents_are_not_fills"])
        self.assertFalse(report["live_execution_authorized"])
        self.assertEqual(report["regime_observation_counts"]["trending"], 1)
        self.assertEqual(report["missed_signal_reasons"]["LOW_CONFIDENCE"], 1)

    def test_old_and_future_events_are_not_in_24h_window(self):
        now = datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc)
        def event(eid, stamp):
            return {
                "sequence": 1, "event_id": eid, "event_type": "MISSED_SIGNAL",
                "occurred_at_utc": stamp.isoformat(), "payload_json": "{}",
            }
        report = build_nightly_report([
            event("old", now - timedelta(hours=25)),
            event("future", now + timedelta(seconds=1)),
        ], generated_at_utc=now)
        self.assertEqual(report["event_counts_24h"], {})

    def test_schema_diff_is_observational_only(self):
        diff = schema_diff(
            {"old": "str", "confidence": 0.5},
            {"confidence": 0.7, "new": True},
        )
        self.assertEqual(diff["added"], ["new"])
        self.assertEqual(diff["removed"], ["old"])
        self.assertEqual(diff["changed"][0]["field"], "confidence")
        self.assertTrue("auto_rewrite" not in diff)

    def test_malformed_event_is_counted_not_crashed(self):
        now = datetime.now(timezone.utc)
        report = build_nightly_report([{
            "event_id": "bad", "event_type": "MISSED_SIGNAL",
            "occurred_at_utc": now.isoformat(), "payload_json": "{no-json",
        }], generated_at_utc=now)
        self.assertEqual(report["malformed_events_skipped"], 1)

    def test_read_only_database_and_atomic_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "events.sqlite3"
            with PaperEventLedger(db_path) as ledger:
                ledger.append(
                    event_id="intent-1", event_type="PAPER_INTENT",
                    payload={"decision": {"regime": "trending", "confidence": 0.72}},
                )
                self.assertTrue(ledger.verify_chain())
            rows = read_events_readonly(db_path)
            self.assertEqual(len(rows), 1)
            out_path = Path(tmp) / "results" / "nightly.json"
            report = build_nightly_report(rows)
            written = write_report_atomic(out_path, report)
            self.assertEqual(written, out_path)
            decoded = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertFalse(decoded["performance_claims_permitted"])
            with sqlite3.connect(db_path) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM paper_events").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
