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
    def _write_evidence(root: Path, valid_until: datetime, balance: float = 1.45) -> None:
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
                "balance": balance,
                "available_balance": balance,
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

    def test_starting_stake_requires_minimum_available_balance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_evidence(
                root,
                datetime.now(timezone.utc) + timedelta(minutes=5),
                balance=0.50,
            )
            report = evaluate(root)
        gate = next(
            item for item in report["blockers"] if item["gate"] == "STAKE_AFFORDABILITY"
        )
        self.assertEqual("FAIL", gate["status"])
        self.assertIn(">= 1.00", gate["reason"])
        self.assertFalse(report["final_execution_authorization"])

    def test_starting_stake_is_affordable_only_with_current_balance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_evidence(
                root,
                datetime.now(timezone.utc) + timedelta(minutes=5),
                balance=1.45,
            )
            report = evaluate(root)
        gate = next(
            item for item in report["blockers"] if item["gate"] == "STAKE_AFFORDABILITY"
        )
        self.assertEqual("PASS", gate["status"])
        self.assertEqual(1.0, report["capital"]["execution_minimum_stake"])
        self.assertEqual(1.0, report["capital"]["starting_stake"])

    def test_missing_evidence_cannot_be_upgraded_by_environment_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate(Path(tmp))
        self.assertEqual("UNKNOWN", report["deriv"]["session"])
        self.assertFalse(report["deriv"]["balance_fresh"])

    def test_invalid_auth_mode_cannot_pass_credentials_gate(self) -> None:
        os.environ.update({
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_EXPECTED_LOGINID": "",
            "DERIV_AUTHORIZED_ACCOUNT_ID": "CRTEST",
            "DERIV_APP_ID": "12345",
            "DERIV_AUTH_MODE": "deriv_auth_token",
            "DERIV_EXPECTED_CURRENCY": "USD",
        })
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate(Path(tmp))
        self.assertFalse(report["deriv"]["credentials_present"])
        credentials_gate = next(
            gate for gate in report["blockers"] if gate["gate"] == "DERIV_CREDENTIALS"
        )
        self.assertEqual(credentials_gate["status"], "FAIL")

    def test_oauth_accepts_authorized_account_alias_without_pat_app_id(self) -> None:
        os.environ.update({
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_EXPECTED_LOGINID": "",
            "DERIV_AUTHORIZED_ACCOUNT_ID": "CRTEST",
            "DERIV_APP_ID": "",
            "DERIV_AUTH_MODE": "oauth",
            "DERIV_EXPECTED_CURRENCY": "USD",
        })
        with tempfile.TemporaryDirectory() as tmp:
            report = evaluate(Path(tmp))
        self.assertTrue(report["deriv"]["credentials_present"])

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
