from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.sanitize_deriv_readonly_evidence import build_summary


ROOT = Path(__file__).resolve().parents[1]


class WorkflowSecretIsolationTests(unittest.TestCase):
    def test_general_ci_has_no_production_environment_or_secret_expressions(self):
        workflow = (ROOT / ".github/workflows/aurelia-assurance.yml").read_text(encoding="utf-8")
        self.assertNotIn("environment: production", workflow)
        self.assertNotIn("${{ secrets.", workflow)
        self.assertNotIn("${{ vars.DERIV_AUTH_MODE", workflow)

    def test_authenticated_workflow_is_manual_main_only_and_protected(self):
        workflow = (ROOT / ".github/workflows/deriv-readonly-verification.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)
        self.assertIn("environment: production", workflow)
        self.assertIn("DERIV_LIFECYCLE_MODE: VERIFY_ONLY", workflow)
        self.assertIn("Upload sanitized evidence only", workflow)

    def test_verify_only_lifecycle_branch_has_no_executor_execution_call(self):
        source = (ROOT / "scripts/verify_deriv_transaction_lifecycle.py").read_text(encoding="utf-8")
        verify_only = source.split('if mode == "VERIFY_ONLY":', 1)[1].split("decision_payload =", 1)[0]
        self.assertNotIn("executor.execute(", verify_only)
        self.assertIn('"broker_submission_performed": False', verify_only)
        self.assertIn('"capital_movement": False', verify_only)

    def test_sanitizer_excludes_account_balance_and_transaction_identifiers(self):
        def evidence(scope, observed, verification_scope):
            value = {
                "evidence_id": "evidence-2026-10-21T12:00:00Z",
                "source_hash": "commit-abc",
                "config_hash": "config-def",
                "data_hash": "data-hash",
                "started_at_utc": "2026-10-21T12:00:00+00:00",
                "ended_at_utc": "2026-10-21T12:01:00+00:00",
                "valid_until_utc": "2026-10-21T12:06:00+00:00",
                "verification_scope": verification_scope,
                "result": "PROVEN",
                "status": "CURRENT",
                "orders_submitted": 0,
                "capital_authority_granted": False,
                "order_submission_permitted": False,
                "observed": observed,
            }
            canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            value["record_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            return value

        session = evidence("session", {
            "account_loginid": "PRIVATE_LOGIN_1234",
            "environment": "real",
            "currency": "USD",
            "balance": 1234.56,
            "available_balance": 1234.56,
        }, "AUTHENTICATED_DERIV_REAL_SESSION")
        broker = evidence("broker", {
            "account_loginid": "PRIVATE_LOGIN_1234",
            "environment": "real",
            "currency": "USD",
            "available_balance": 1234.56,
            "capital_movement_performed_by_verifier": False,
            "broker_buy_transaction_ids": ["PRIVATE_TX_456"],
            "open_contract_ids": ["PRIVATE_CONTRACT_789"],
        }, "REAL_DERIV_BROKER_ACCOUNT_READ_ONLY")
        lifecycle = evidence("lifecycle", {
            "mode": "VERIFY_ONLY",
            "environment": "real",
            "broker_submission_performed": False,
            "capital_movement": False,
        }, "REAL_DERIV_LIFECYCLE_VERIFY_ONLY")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, row in (("session", session), ("broker", broker), ("lifecycle", lifecycle)):
                (root / f"{name}.json").write_text(json.dumps(row), encoding="utf-8")
            result = build_summary(root / "session.json", root / "broker.json", root / "lifecycle.json")
        encoded = json.dumps(result)
        for private_value in ("PRIVATE_LOGIN_1234", "1234.56", "PRIVATE_TX_456", "PRIVATE_CONTRACT_789"):
            self.assertNotIn(private_value, encoded)
        self.assertEqual(result["checks"]["orders_submitted"], 0)
        self.assertIs(result["checks"]["capital_movement"], False)
        self.assertIs(result["checks"]["order_submission_permitted"], False)
        self.assertTrue(result["sensitive_fields_redacted"])
        self.assertEqual(len(result["summary_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
