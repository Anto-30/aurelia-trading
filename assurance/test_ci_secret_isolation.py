"""Regression tests for production credential isolation on untrusted refs."""
from __future__ import annotations

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
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            end = index
            break
    return "\n".join(lines[start:end])


class ProductionSecretIsolationTests(unittest.TestCase):
    def test_general_assurance_has_no_production_environment_or_secrets(self):
        text = (WORKFLOWS / "aurelia-assurance.yml").read_text(encoding="utf-8")
        self.assertNotIn("environment: production", text)
        self.assertNotIn("${{ secrets.", text)
        self.assertNotIn("verify_deriv_session.py", text)

    def test_account_verification_is_blocked_without_trade_scoped_credentials(self):
        text = (WORKFLOWS / "deriv-auth-evidence.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'", text)
        self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", text)
        self.assertIn("DERIV_ACCOUNT_EVIDENCE=BLOCKED", text)
        self.assertNotIn("environment: production", text)
        self.assertNotIn("${{ secrets.", text)
        self.assertNotIn("DERIV_AUTH_TOKEN", text)
        self.assertNotIn("DERIV_PAT", text)
        self.assertNotIn("verify_deriv_session.py", text)

    def test_verifier_script_never_reads_secrets_or_constructs_authenticated_session(self):
        source = (ROOT / "scripts" / "verify_deriv_session.py").read_text(encoding="utf-8")
        self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", source)
        self.assertNotIn("get_optional_secret", source)
        self.assertNotIn("DerivSessionManager", source)
        self.assertNotIn("DerivAdapter", source)
        self.assertNotIn("DERIV_AUTH_TOKEN", source)
        self.assertNotIn("DERIV_PAT", source)

    def test_bearer_tokens_are_used_only_in_live_gated_deployment_steps(self):
        text = (WORKFLOWS / "self-hosted-runtime-deploy.yml").read_text(encoding="utf-8")
        self.assertNotIn("vars.DERIV_AUTH_TOKEN", text)
        self.assertNotIn("vars.DERIV_PAT", text)
        self.assertIn("secrets.DERIV_AUTH_TOKEN", text)
        self.assertIn("secrets.DERIV_PAT", text)
        deploy_job = _job_block("self-hosted-runtime-deploy.yml", "deploy")
        for block in deploy_job.split("      - name: ")[1:]:
            if "secrets.DERIV_AUTH_TOKEN" in block or "secrets.DERIV_PAT" in block:
                self.assertIn("if: inputs.deployment_mode == 'LIVE'", block)

    def test_non_secret_account_configuration_uses_protected_variables_or_boolean_presence(self):
        for name in ("secret-presence-report.yml", "self-hosted-runtime-deploy.yml"):
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            for key in DERIV_CONFIG_KEYS:
                self.assertIn("vars." + key, text)
        report = (WORKFLOWS / "secret-presence-report.yml").read_text(encoding="utf-8")
        self.assertIn("secrets.DERIV_APP_ID != ''", report)
        self.assertIn("secrets.DERIV_EXPECTED_LOGINID != ''", report)
        self.assertIn("secrets.DERIV_EXPECTED_CURRENCY != ''", report)
        self.assertIn("vars.DERIV_AUTH_MODE", report)
        self.assertIn("vars.DERIV_ENVIRONMENT", report)
        self.assertNotIn("DERIV_AUTH_TOKEN: ${{ secrets.", report)

    def test_session_verification_alias_is_non_executing_and_credential_free(self):
        text = (WORKFLOWS / "deriv-session-verification.yml").read_text(encoding="utf-8")
        self.assertIn("DERIV_SESSION_VERIFICATION=NOT_EXECUTED", text)
        self.assertIn("NEXT_STEP=MANUALLY_DISPATCH_DERIV_AUTH_EVIDENCE_ON_MAIN", text)
        self.assertNotIn("environment: production", text)
        self.assertNotIn("${{ secrets.", text)
        self.assertNotIn("DERIV_AUTH_TOKEN", text)

    def test_whatsapp_alert_secrets_are_manual_main_only_and_environment_protected(self):
        text = (WORKFLOWS / "aurelia-free-runtime.yml").read_text(encoding="utf-8")
        alert_job = _job_block("aurelia-free-runtime.yml", "whatsapp-alert-smoke")
        self.assertIn("github.event_name == 'workflow_dispatch'", alert_job)
        self.assertIn("github.ref == 'refs/heads/main'", alert_job)
        self.assertIn("environment: production", alert_job)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("pull_request_target:", text)
        self.assertIn("secrets.TWILIO_ACCOUNT_SID", alert_job)
        self.assertIn("secrets.TWILIO_AUTH_TOKEN", alert_job)
        self.assertNotIn("secrets.TWILIO_ACCOUNT_SID", _job_block("aurelia-free-runtime.yml", "runtime-probe"))

    def test_presence_report_secret_expressions_are_boolean_only(self):
        text = (WORKFLOWS / "secret-presence-report.yml").read_text(encoding="utf-8")
        for line in text.splitlines():
            if "${{ secrets." in line:
                self.assertTrue(" != '' }}" in line or " == 'USD' }}" in line, line)
        self.assertNotIn("DERIV_AUTH_TOKEN: ${{ secrets.DERIV_AUTH_TOKEN ||", text)
        self.assertNotIn("AURELIA_SSH_KEY: ${{ secrets.AURELIA_SSH_KEY }}", text)
        self.assertNotIn("AURELIA_ATTESTATION_SIGNING_KEY: ${{ secrets.AURELIA_ATTESTATION_SIGNING_KEY }}", text)

    def test_live_account_verification_blocks_before_trade_token_mapping(self):
        workflow = (WORKFLOWS / "self-hosted-runtime-deploy.yml").read_text(encoding="utf-8")
        self.assertIn(
            "Block LIVE deployment while Deriv read-only account scope is unavailable",
            workflow,
        )
        self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", workflow)
        blocked_at = workflow.index(
            "Block LIVE deployment while Deriv read-only account scope is unavailable"
        )
        token_refs = [
            match.start()
            for match in re.finditer(r"secrets\\.(?:DERIV_AUTH_TOKEN|DERIV_PAT)", workflow)
        ]
        self.assertTrue(token_refs)
        self.assertTrue(all(index > blocked_at for index in token_refs))
        for step_name in (
            "Require explicit Deriv account bindings for LIVE verification",
            "Generate fresh authenticated real-account evidence without submitting orders",
            "Refresh readiness from current evidence; remain fail-closed on any blocker",
            "Require deterministic live release gate for LIVE deployment",
        ):
            self.assertNotIn(step_name, workflow)
        token_blocks = [
            block
            for block in _job_block("self-hosted-runtime-deploy.yml", "deploy").split("      - name: ")[1:]
            if "secrets.DERIV_AUTH_TOKEN" in block or "secrets.DERIV_PAT" in block
        ]
        self.assertEqual(len(token_blocks), 1)
        self.assertIn("Provision LIVE runtime secrets to root-only host store", token_blocks[0])
        self.assertIn("if: inputs.deployment_mode == 'LIVE'", token_blocks[0])

    def test_verify_only_runtime_never_loads_legacy_trade_scoped_readonly_file(self):
        source = (ROOT / "scripts" / "deploy" / "bootstrap_and_deploy.sh").read_text(encoding="utf-8")
        self.assertIn('sudo rm -f "$READONLY_SECRET_FILE"', source)
        self.assertNotIn('ENV_FILES+=("$READONLY_SECRET_FILE")', source)
        self.assertNotIn('elif [ -f "$READONLY_SECRET_FILE" ]', source)
        self.assertNotIn('VERIFY_DERIV_AUTH="$AUTH_CONFIGURED"', source)
        self.assertIn("VERIFY_DERIV_AUTH=false", source)
        self.assertNotIn("provision_deriv_readonly_secrets.py", source)

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
        self.assertNotIn("${{ secrets.", text)

    def test_presence_report_is_manual_main_only_and_boolean_only(self):
        text = (WORKFLOWS / "secret-presence-report.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("environment: production", text)
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'", text)
        self.assertIn("DERIV_AUTH_TOKEN_PRESENT:", text)
        self.assertIn("secrets.DERIV_AUTH_TOKEN != ''", text)
        self.assertNotIn("DERIV_AUTH_TOKEN: ${{ secrets.DERIV_AUTH_TOKEN", text)
        self.assertIn("Report boolean-only production secret presence", text)

    def test_self_hosted_deployment_credentials_are_live_lock_gated_and_main_only(self):
        workflow = (WORKFLOWS / "self-hosted-runtime-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'", workflow)
        deploy_job = _job_block("self-hosted-runtime-deploy.yml", "deploy")
        job_env = deploy_job.split("steps:", 1)[0]
        self.assertNotIn("${{ secrets.", job_env)
        lock_gate = workflow.index("name: Verify source revision and deployment lock")
        first_deriv_secret = min(
            workflow.index(marker)
            for marker in ("secrets.DERIV_AUTH_TOKEN", "secrets.DERIV_PAT")
        )
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
