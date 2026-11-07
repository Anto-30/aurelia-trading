"""Regression tests for protecting production secrets from untrusted Git refs."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


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

    def test_all_protected_secret_workflows_require_manual_main_dispatch(self):
        cases = (
            ("deriv-auth-evidence.yml", "verify"),
            ("deriv-session-verification.yml", "verify"),
            ("deriv-verify-only-lifecycle.yml", "verify-only"),
            ("self-hosted-runtime-deploy.yml", "deploy"),
            ("aurelia-free-runtime.yml", "authenticated-deriv-evidence"),
            ("aurelia-free-runtime.yml", "deriv-lifecycle-verify-only"),
            ("aurelia-free-runtime.yml", "whatsapp-alert-smoke"),
        )
        expected = "if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}"
        for workflow, job in cases:
            with self.subTest(workflow=workflow, job=job):
                block = _job_block(workflow, job)
                self.assertIn(expected, block)
                self.assertRegex(block, r"\$\{\{\s*secrets\.")

    def test_auth_evidence_is_not_scheduled(self):
        text = (WORKFLOWS / "deriv-auth-evidence.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)

    def test_secret_presence_report_is_main_only(self):
        block = _job_block("secret-presence-report.yml", "report")
        self.assertIn("if: ${{ github.ref == 'refs/heads/main' }}", block)
        self.assertRegex(block, r"\$\{\{\s*secrets\.")

    def test_pull_request_trigger_remains_available_without_secret_access(self):
        text = (WORKFLOWS / "aurelia-assurance.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", text)
        self.assertIn('branches: ["**"]', text)


if __name__ == "__main__":
    unittest.main()
