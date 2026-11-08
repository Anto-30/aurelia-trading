"""Regression tests for PR secret isolation and Deriv account-scope policy."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DERIV_SECRET_MARKERS = (
    "DERIV_AUTH_TOKEN",
    "DERIV_PAT",
    "DERIV_APP_ID",
    "DERIV_EXPECTED_LOGINID",
    "DERIV_AUTHORIZED_ACCOUNT_ID",
    "DERIV_EXPECTED_CURRENCY",
)


def _job_block(workflow_name: str, job_name: str) -> str:
    lines = (WORKFLOWS / workflow_name).read_text(encoding="utf-8").splitlines()
    marker = f"  {job_name}:"
    try:
        start = lines.index(marker)
    except ValueError as exc:
        raise AssertionError(
            f"Required job {job_name!r} missing from {workflow_name}"
        ) from exc
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.match(r"^  [A-Za-z0-9_-]+:\s*$", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


class ProductionSecretIsolationTests(unittest.TestCase):
    def test_general_assurance_has_no_production_environment_or_secrets(self):
        text = (WORKFLOWS / "aurelia-assurance.yml").read_text(encoding="utf-8")
        self.assertNotIn("environment: production", text)
        self.assertNotRegex(text, r"\$\{\{\s*secrets\.")
        self.assertNotIn("DERIV_AUTH_CONFIGURED", text)
        self.assertNotIn("verify_deriv_session.py", text)
        self.assertNotIn("deriv-auth-verification:", text)

    def test_account_verification_workflows_are_blocked_and_credential_free(self):
        for filename in (
            "deriv-auth-evidence.yml",
            "deriv-session-verification.yml",
            "deriv-verify-only-lifecycle.yml",
        ):
            with self.subTest(workflow=filename):
                text = (WORKFLOWS / filename).read_text(encoding="utf-8")
                self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", text)
                self.assertNotIn("environment: production", text)
                self.assertNotRegex(text, r"\$\{\{\s*secrets\.")
                for marker in DERIV_SECRET_MARKERS:
                    self.assertNotIn(marker, text)

    def test_free_runtime_retains_only_public_deriv_probe(self):
        text = (WORKFLOWS / "aurelia-free-runtime.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/verify_deriv_public_transport.py", text)
        self.assertIn('AURELIA_VERIFY_DERIV_AUTH: "false"', text)
        self.assertNotIn("DERIV_AUTH_CONFIGURED", text)
        self.assertNotIn("verify_deriv_session.py", text)
        self.assertNotIn("verify_deriv_transaction_lifecycle.py", text)
        self.assertNotIn("environment: production", text)
        for marker in DERIV_SECRET_MARKERS:
            self.assertNotIn(marker, text)

    def test_whatsapp_smoke_remains_main_only_and_separate_from_deriv(self):
        block = _job_block("aurelia-free-runtime.yml", "whatsapp-alert-smoke")
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}", block)
        self.assertIn("TWILIO_AUTH_TOKEN", block)
        self.assertNotIn("DERIV_AUTH_TOKEN", block)

    def test_secret_presence_report_is_main_only(self):
        block = _job_block("secret-presence-report.yml", "report")
        job_conditions = re.findall(r"^    if:\s*(.+)$", block, flags=re.MULTILINE)
        self.assertEqual(
            job_conditions,
            ["${{ github.ref == 'refs/heads/main' }}"],
            "Secret-presence report must have exactly one main-only job condition",
        )
        self.assertRegex(block, r"\$\{\{\s*secrets\.")

    def test_pull_request_trigger_remains_available_without_secret_access(self):
        text = (WORKFLOWS / "aurelia-assurance.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", text)
        self.assertIn('branches: ["**"]', text)


if __name__ == "__main__":
    unittest.main()
