"""Regression tests for production credential isolation on untrusted refs."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SECRET_ENV_KEYS = (
    "DERIV_AUTH_TOKEN",
    "DERIV_APP_ID",
    "DERIV_EXPECTED_LOGINID",
    "DERIV_EXPECTED_CURRENCY",
)


def _job_block(workflow_name: str, job_name: str) -> str:
    lines = (WORKFLOWS / workflow_name).read_text(encoding="utf-8").splitlines()
    marker = f"  {job_name}:"
    try:
        start = lines.index(marker)
    except ValueError as exc:
        raise AssertionError(f"Required job {job_name!r} missing from {workflow_name}") from exc
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

    def test_canonical_account_verifier_is_manual_main_only(self):
        text = (WORKFLOWS / "deriv-auth-evidence.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'", text)
        self.assertIn("environment: production", text)
        self.assertIn("run: python scripts/verify_deriv_session.py", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("pull_request:", text)

    def test_session_verification_alias_cannot_access_credentials(self):
        text = (WORKFLOWS / "deriv-session-verification.yml").read_text(encoding="utf-8")
        self.assertIn("RUN_AURELIA_DERIV_ACCOUNT_IDENTITY_EVIDENCE_ON_MAIN=true", text)
        self.assertNotIn("environment: production", text)
        self.assertNotRegex(text, r"\$\{\{\s*secrets\.")
        self.assertNotIn("DERIV_AUTH_TOKEN", text)

    def test_credentials_are_scoped_to_canonical_verifier_step_only(self):
        block = _job_block("deriv-auth-evidence.yml", "verify")
        pre_steps = block.split("steps:", 1)[0]
        self.assertNotRegex(pre_steps, r"\$\{\{\s*secrets\.")
        for key in SECRET_ENV_KEYS:
            self.assertRegex(block, rf"(?m)^\s+{key}: \$\{{\{{ secrets\.")

    def test_public_runtime_has_no_deriv_credentials(self):
        text = (WORKFLOWS / "aurelia-free-runtime.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/verify_deriv_public_transport.py", text)
        self.assertIn('AURELIA_VERIFY_DERIV_AUTH: "false"', text)
        for key in SECRET_ENV_KEYS:
            self.assertNotIn(key, text)
        self.assertNotIn("verify_deriv_session.py", text)
        self.assertNotIn("verify_deriv_transaction_lifecycle.py", text)

    def test_transaction_lifecycle_workflow_remains_held(self):
        text = (WORKFLOWS / "deriv-verify-only-lifecycle.yml").read_text(encoding="utf-8")
        self.assertIn("VERIFY_ONLY_LIFECYCLE_REQUIRES_SEPARATE_NO_ORDER_ACTION_AUDIT", text)
        self.assertNotRegex(text, r"\$\{\{\s*secrets\.")

    def test_secret_presence_report_is_main_only(self):
        block = _job_block("secret-presence-report.yml", "report")
        conditions = re.findall(r"^    if:\s*(.+)$", block, flags=re.MULTILINE)
        self.assertEqual(conditions, ["${{ github.ref == 'refs/heads/main' }}"])
            self.assertRegex(block, rf"(?m)^\s+{key}: \$\{{\{{ secrets\.")

    def test_whatsapp_smoke_remains_main_only_and_separate_from_deriv(self):
        block = _job_block("aurelia-free-runtime.yml", "whatsapp-alert-smoke")
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}", block)
        self.assertIn("TWILIO_AUTH_TOKEN", block)
        self.assertNotIn("DERIV_AUTH_TOKEN", block)

    def test_pull_request_trigger_remains_credential_free(self):
        text = (WORKFLOWS / "aurelia-assurance.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", text)
        self.assertIn('branches: ["**"]', text)


if __name__ == "__main__":
    unittest.main()
