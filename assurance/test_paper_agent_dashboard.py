"""Tests for the read-only paper decision dashboard."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.paper_agent.dashboard import build_dashboard_snapshot, verify_events_hash_chain, serve_dashboard
from research.paper_agent.ledger import PaperEventLedger
from research.paper_agent.report import read_events_readonly


class PaperDashboardTests(unittest.TestCase):
    def test_dashboard_exposes_events_but_never_fake_pnl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.sqlite3"
            with PaperEventLedger(path) as ledger:
                ledger.append(
                    event_id="p1", event_type="PAPER_INTENT",
                    payload={
                        "status": "WOULD_TRADE",
                        "allowed_by_risk_gate": True,
                        "decision": {"regime": "trending", "direction": "long", "confidence": 0.72},
                        "untrusted_secret": "never-return-this",
                    },
                )
                ledger.append(
                    event_id="m1", event_type="MISSED_SIGNAL",
                    payload={"reason": "CONFIDENCE_BELOW_0_70"},
                )
            rows = read_events_readonly(path)
            snapshot = build_dashboard_snapshot(
                rows, generated_at_utc=datetime.now(timezone.utc)
            )
            self.assertEqual(snapshot["ledger_integrity"], "VALID")
            self.assertEqual(snapshot["paper_intents_24h"], 1)
            self.assertEqual(snapshot["missed_signals_24h"], 1)
            self.assertIsNone(snapshot["pnl"])
            self.assertIsNone(snapshot["win_rate"])
            self.assertEqual(snapshot["open_positions"], [])
            self.assertFalse(snapshot["live_execution_authorized"])
            serialized = json.dumps(snapshot)
            self.assertNotIn("never-return-this", serialized)

    def test_dashboard_latches_after_persisted_kill_switch_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.sqlite3"
            with PaperEventLedger(path) as ledger:
                ledger.append(
                    event_id="kill-1", event_type="KILL_SWITCH_TRIPPED",
                    payload={"reason": "CRISIS_REGIME", "reasons": ["CRISIS_REGIME"]},
                )
            snapshot = build_dashboard_snapshot(read_events_readonly(path))
            self.assertEqual(snapshot["kill_switch_state"], "LATCHED")

    def test_dashboard_marks_hash_chain_invalid_as_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.sqlite3"
            with PaperEventLedger(path) as ledger:
                ledger.append(event_id="e1", event_type="SYSTEM_ALERT", payload={"ok": True})
            with sqlite3.connect(path) as db:
                db.execute("DROP TRIGGER paper_events_no_update")
                db.execute("UPDATE paper_events SET payload_json='{}' WHERE event_id='e1'")
            rows = read_events_readonly(path)
            self.assertFalse(verify_events_hash_chain(rows))
            snapshot = build_dashboard_snapshot(rows)
            self.assertEqual(snapshot["system_status"], "BLOCKED_LEDGER_INTEGRITY_INVALID")
            self.assertEqual(snapshot["kill_switch_state"], "BLOCKED_LEDGER_INTEGRITY_INVALID")
            self.assertFalse(snapshot["live_execution_authorized"])

    def test_public_network_bind_is_refused(self):
        with self.assertRaisesRegex(ValueError, "MUST_BIND_TO_LOOPBACK"):
            serve_dashboard("/path/not/read", host="0.0.0.0", port=8765)


if __name__ == "__main__":
    unittest.main()
