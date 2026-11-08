"""Regression tests for untrusted-ref isolation and Deriv account-scope policy."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DERIV_SECRET_EXPR = re.compile(
    r"\$\{\{\s*secrets\.DERIV_(?:AUTH_TOKEN|PAT|APP_ID|EXPECTED_LOGINID|AUTHORIZED_ACCOUNT_ID|EXPECTED_CURRENCY)\b"
)


def read_workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


class ProductionSecretIsolationTests(unittest.TestCase):
    def test_general_assurance_remains_untrusted_ref_safe(self):
        text = read_workflow("aurelia-assurance.yml")
        self.assertIn("pull_request:", text)
        self.assertIn('branches: ["**"]', text)
        self.assertNotIn("environment: production", text)
        self.assertNotRegex(text, r"\$\{\{\s*secrets\.")
        self.assertNotIn("verify_deriv_session.py", text)
        self.assertNotIn("verify_deriv_transaction_lifecycle.py", text)

    def test_deriv_account_verification_workflows_are_blocked_and_secret_free(self):
        for name in (
            "deriv-auth-evidence.yml",
            "deriv-session-verification.yml",
            "deriv-verify-only-lifecycle.yml",
        ):
            with self.subTest(workflow=name):
                text = read_workflow(name)
                self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", text)
                self.assertNotIn("environment: production", text)
                self.assertNotRegex(text, r"\$\{\{\s*secrets\.")
                self.assertNotIn("DERIV_AUTH_TOKEN", text)
                self.assertNotIn("DERIV_PAT", text)

    def test_no_workflow_maps_trade_scoped_deriv_account_credentials(self):
        offenders = []
        for path in WORKFLOWS.glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            if DERIV_SECRET_EXPR.search(text):
                offenders.append(path.name)
        for path in WORKFLOWS.glob("*.yaml"):
            text = path.read_text(encoding="utf-8")
            if DERIV_SECRET_EXPR.search(text):
                offenders.append(path.name)
        self.assertEqual([], offenders, f"Deriv account credentials injected by workflows: {offenders}")

    def test_free_runtime_keeps_public_market_data_only(self):
        text = read_workflow("aurelia-free-runtime.yml")
        self.assertIn("verify_deriv_public_transport.py", text)
        self.assertIn('AURELIA_VERIFY_DERIV_AUTH: "false"', text)
        self.assertNotIn("DERIV_AUTH_TOKEN", text)
        self.assertNotIn("DERIV_PAT", text)
        self.assertNotIn("environment: production", text)

    def test_secret_presence_report_never_receives_deriv_account_credentials(self):
        text = read_workflow("secret-presence-report.yml")
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertIn("environment: production", text)
        self.assertNotIn("DERIV_AUTH_TOKEN", text)
        self.assertNotIn("DERIV_PAT", text)
        self.assertNotIn("DERIV_APP_ID", text)
        self.assertNotIn("DERIV_EXPECTED_LOGINID", text)
        self.assertNotIn("DERIV_EXPECTED_CURRENCY", text)
        self.assertIn("AURELIA_OPERATOR_RESET_SIGNING_KEY", text)

    def test_secret_presence_report_is_main_only(self):
        text = read_workflow("secret-presence-report.yml")
        block = text.split("  report:", 1)[1]
        self.assertIn("if: ${{ github.ref == 'refs/heads/main' }}", block)
        self.assertIn("LIVE_EXECUTION: \"BLOCKED\"", block)
        self.assertIn('FINAL_EXECUTION_AUTHORIZATION: "false"', block)


if __name__ == "__main__":
    unittest.main()
