"""Regression tests for production credential isolation on untrusted refs."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DERIV_CONFIG_KEYS = ("DERIV_APP_ID", "DERIV_EXPECTED_LOGINID", "DERIV_EXPECTED_CURRENCY")
DERIV_TOKEN_KEYS = ("DERIV_AUTH_TOKEN", "DERIV_PAT")


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
        self.assertNotIn("secrets.", text)
        self.assertNotIn("verify_deriv_session.py", text)

    def test_canonical_account_verifier_is_manual_main_only_and_production_scoped(self):
        text = (WORKFLOWS / "deriv-auth-evidence.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'", text)
        self.assertIn("environment: production", text)
        self.assertIn("run: python scripts/verify_deriv_session.py", text)
        self.assertIn('LIVE_EXECUTION: BLOCKED', text)
        self.assertIn('FINAL_EXECUTION_AUTHORIZATION: "false"', text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("pull_request:", text)

    def test_bearer_token_is_secrets_only(self):
        for name in ("deriv-auth-evidence.yml", "secret-presence-report.yml", "self-hosted-runtime-deploy.yml"):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            self.assertNotIn("vars.DERIV_AUTH_TOKEN", text)
            self.assertNotIn("vars.DERIV_PAT", text)
            if "DERIV_AUTH_TOKEN:" in text:
                self.assertIn("DERIV_AUTH_TOKEN:", text)
                self.assertIn("secrets.DERIV_AUTH_TOKEN", text)
                self.assertIn("secrets.DERIV_PAT", text)

    def test_non_secret_account_configuration_supports_production_variables(self):
        for name in ("deriv-auth-evidence.yml", "secret-presence-report.yml", "self-hosted-runtime-deploy.yml"):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            for key in DERIV_CONFIG_KEYS:
                self.assertIn("vars." + key, text)
        verifier = (WORKFLOWS / "deriv-auth-evidence.yml").read_text(encoding="utf-8")
        report = (WORKFLOWS / "secret-presence-report.yml").read_text(encoding="utf-8")
        self.assertIn("vars.DERIV_AUTH_MODE", verifier)
        self.assertIn("vars.DERIV_ENVIRONMENT", report)

    def test_session_verification_alias_is_non_executing_and_credential_free(self):
        text = (WORKFLOWS / "deriv-session-verification.yml").read_text(encoding="utf-8")
        self.assertIn("DERIV_SESSION_VERIFICATION=NOT_EXECUTED", text)
        self.assertIn("NEXT_STEP=MANUALLY_DISPATCH_DERIV_AUTH_EVIDENCE_ON_MAIN", text)
        self.assertNotIn("environment: production", text)
        self.assertNotIn("secrets.", text)
        self.assertNotIn("DERIV_AUTH_TOKEN", text)

    def test_public_runtime_has_no_deriv_credentials_or_account_settings(self):
        text = (WORKFLOWS / "aurelia-free-runtime.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/verify_deriv_public_transport.py", text)
        self.assertIn('AURELIA_VERIFY_DERIV_AUTH: "false"', text)
        for key in DERIV_TOKEN_KEYS + DERIV_CONFIG_KEYS:
            self.assertNotIn(key, text)
        self.assertNotIn("verify_deriv_session.py", text)

    def test_transaction_lifecycle_workflow_remains_held(self):
        text = (WORKFLOWS / "deriv-verify-only-lifecycle.yml").read_text(encoding="utf-8")
        self.assertIn("VERIFY_ONLY_LIFECYCLE_REQUIRES_SEPARATE_NO_ORDER_ACTION_AUDIT", text)
        self.assertNotIn("secrets.", text)

    def test_presence_report_is_manual_main_only_and_production_scoped(self):
        text = (WORKFLOWS / "secret-presence-report.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("push:", text)
        self.assertIn("environment: production", text)
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'", text)
        self.assertIn("Report production secret and variable presence", text)
        test_step = text.split("      - name: Install test dependency", 1)[1]
        self.assertNotIn("secrets.", test_step)

    def test_self_hosted_deployment_credentials_are_live_lock_gated_and_main_only(self):
        workflow = (WORKFLOWS / "self-hosted-runtime-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'", workflow)
        deploy_job = _job_block("self-hosted-runtime-deploy.yml", "deploy")
        job_env = deploy_job.split("steps:", 1)[0]
        self.assertNotIn("secrets.", job_env)
        lock_gate = workflow.index("name: Verify source revision and deployment lock")
        first_deriv_secret = min(workflow.index(marker) for marker in ("secrets.DERIV_AUTH_TOKEN", "secrets.DERIV_PAT"))
        self.assertLess(lock_gate, first_deriv_secret)
        for block in deploy_job.split("      - name: ")[1:]:
            if "secrets.DERIV_AUTH_TOKEN" in block or "secrets.DERIV_PAT" in block:
                self.assertIn("if: inputs.deployment_mode == 'LIVE'", block)
        lock = (ROOT / "config" / "LIVE_LOCK.yaml").read_text(encoding="utf-8")
        self.assertIn("live_trading_enabled: false", lock)
        self.assertIn("FINAL_EXECUTION_AUTHORIZATION: false", lock)
        self.assertIn("LIVE_EXECUTION: BLOCKED", lock)
        self.assertIn("capital_plane_mode: VERIFY_ONLY", lock)


if __name__ == "__main__":
    unittest.main()
