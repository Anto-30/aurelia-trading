from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runtime.ops.readiness_orchestrator import evaluate


class ReadinessEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = dict(os.environ)
        os.environ["AURELIA_DERIV_SESSION_VERIFIED"] = "true"
        os.environ["AURELIA_BALANCE_VERIFIED"] = "true"
        os.environ["AURELIA_VERIFIED_AVAILABLE_BALANCE"] = "1.45"
        os.environ["AURELIA_DERIV_REST_VERIFIED"] = "true"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self.original)

    @staticmethod
    def _write_evidence(root: Path, valid_until: datetime) -> None:
        path = root / "artifacts" / "deriv_authenticated_session.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "evidence_id": "test",
                    "status": "CURRENT",
                    "result": "PROVEN",
                    "valid_until_utc": valid_until.isoformat(),
                    "record_hash": "test-hash",
                }
            ),
            encoding="utf-8",
        )

    def test_session_and_balance_require_current_proven_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_evidence(root, datetime.now(timezone.utc) + timedelta(minutes=5))
            report = evaluate(root)
        self.assertEqual("VERIFIED", report["deriv"]["session"])
        self.assertTrue(report["deriv"]["balance_fresh"])

    def test_missing_evidence_cannot_be_upgraded_by_environment_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate(Path(tmp))
        self.assertEqual("UNKNOWN", report["deriv"]["session"])
        self.assertFalse(report["deriv"]["balance_fresh"])

    def test_expired_evidence_returns_to_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_evidence(root, datetime.now(timezone.utc) - timedelta(seconds=1))
            report = evaluate(root)
        self.assertEqual("UNKNOWN", report["deriv"]["session"])
        self.assertFalse(report["deriv"]["balance_fresh"])


if __name__ == "__main__":
    unittest.main()
