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
    def test_pull_request_assurance_job_has_no_production_secrets(self):
        block = _job_block("aurelia-assurance.yml", "assurance")
        self.assertNotIn("environment: production", block)
        self.assertNotRegex(block, r"\$\{\{\s*secrets\.")
        self.assertNotIn("DERIV_AUTH_CONFIGURED", block)
        self.assertNotIn("verify_deriv_session.py", block)

    def test_deriv_auth_job_is_restricted_to_main_push(self):
        block = _job_block("aurelia-assurance.yml", "deriv-auth-verification")
        self.assertIn(
            "if: ${{ github.event_name == 'push' && github.ref == 'refs/heads/main' }}",
            block,
        )
        self.assertIn("environment: production", block)
        self.assertRegex(block, r"\$\{\{\s*secrets\.DERIV_AUTH_TOKEN")

    def test_manual_and_scheduled_secret_workflows_are_main_only(self):
        cases = (
            ("deriv-auth-evidence.yml", "verify", True),
            ("deriv-session-verification.yml", "verify", True),
            ("deriv-verify-only-lifecycle.yml", "verify-only", True),
            ("self-hosted-runtime-deploy.yml", "deploy", True),
            ("aurelia-free-runtime.yml", "authenticated-deriv-evidence", True),
            ("aurelia-free-runtime.yml", "deriv-lifecycle-verify-only", True),
            ("aurelia-free-runtime.yml", "whatsapp-alert-smoke", False),
            ("secret-presence-report.yml", "report", True),
        )
        expected = "if: ${{ github.ref == 'refs/heads/main' }}"
        for workflow, job, uses_environment in cases:
            with self.subTest(workflow=workflow, job=job):
                block = _job_block(workflow, job)
                self.assertIn(expected, block)
                self.assertRegex(block, r"\$\{\{\s*secrets\.")
                if uses_environment:
                    self.assertIn("environment:", block)

    def test_pull_request_trigger_remains_available_without_secret_access(self):
        text = (WORKFLOWS / "aurelia-assurance.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", text)
        self.assertIn('branches: ["**"]', text)


if __name__ == "__main__":
    unittest.main()
