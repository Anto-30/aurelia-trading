from __future__ import annotations

import hashlib
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
        record = {
            "evidence_id": "test",
            "source_hash": "source",
            "artifact_hash": "artifact",
            "config_hash": "config",
            "data_hash": "data",
            "environment": "real",
            "started_at_utc": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            "ended_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "CURRENT",
            "valid_until_utc": valid_until.isoformat(),
            "result": "PROVEN",
            "invariants_checked": ["fresh_balance", "no_orders"],
            "invariants_failed": [],
            "observed": {
                "account_loginid": "CRTEST",
                "account_type": "real",
                "environment": "real",
                "currency": "USD",
                "balance": 1.45,
                "available_balance": 1.45,
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            "orders_submitted": 0,
            "capital_authority_granted": False,
            "provenance": {
                "origin": "ci",
                "issuer": "test-suite",
                "source_commit": "TEST",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        }
        canonical = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        record["record_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        path.write_text(json.dumps(record), encoding="utf-8")

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

    def test_tampered_evidence_returns_to_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_evidence(root, datetime.now(timezone.utc) + timedelta(minutes=5))
            path = root / "artifacts" / "deriv_authenticated_session.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["observed"]["available_balance"] = 99.0
            path.write_text(json.dumps(record), encoding="utf-8")
            report = evaluate(root)
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
