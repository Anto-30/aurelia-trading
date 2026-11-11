"""Semantic regression tests for production secret isolation in GitHub Actions."""
from __future__ import annotations

import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DERIV_CONFIG_KEYS = ("DERIV_APP_ID", "DERIV_EXPECTED_LOGINID", "DERIV_EXPECTED_CURRENCY")
DERIV_TOKEN_KEYS = ("DERIV_AUTH_TOKEN", "DERIV_PAT")
GH_SECRET_PREFIX = "${{ secrets."


def _workflow(name: str) -> dict:
    parsed = yaml.load((WORKFLOWS / name).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(parsed, dict):
        raise AssertionError(f"Workflow {name!r} must parse to a mapping")
    return parsed


def _job(workflow: dict, job_name: str) -> dict:
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or not isinstance(jobs.get(job_name), dict):
        raise AssertionError(f"Required job {job_name!r} missing")
    return jobs[job_name]


def _steps(job: dict) -> list[dict]:
    steps = job.get("steps")
    if not isinstance(steps, list):
        raise AssertionError("Expected workflow job steps to be a sequence")
    return steps


def _step(job: dict, name: str) -> dict:
    found = [step for step in _steps(job) if step.get("name") == name]
    if len(found) != 1:
        raise AssertionError(f"Expected exactly one step named {name!r}, found {len(found)}")
    return found[0]


def _strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)
    elif isinstance(value, str):
        yield value


def _secret_references(value) -> list[str]:
    return [item for item in _strings(value) if GH_SECRET_PREFIX in item]


class ProductionSecretIsolationTests(unittest.TestCase):
    def test_general_assurance_is_pr_safe_and_has_no_production_secrets(self):
        workflow = _workflow("aurelia-assurance.yml")
        self.assertIn("pull_request", workflow["on"])
        self.assertIn("push", workflow["on"])
        assurance = _job(workflow, "assurance")
        self.assertNotEqual(assurance.get("environment"), "production")
        self.assertEqual(_secret_references(workflow), [])

    def test_account_verification_is_manual_main_only_and_credential_free(self):
        workflow = _workflow("deriv-auth-evidence.yml")
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(workflow.get("permissions"), {})
        blocked = _job(workflow, "blocked")
        self.assertIn("github.event_name == 'workflow_dispatch'", blocked.get("if", ""))
        self.assertIn("github.ref == 'refs/heads/main'", blocked.get("if", ""))
        self.assertEqual(_secret_references(workflow), [])
        output = "\n".join(step.get("run", "") for step in _steps(blocked))
        self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", output)
        self.assertIn("DERIV_ACCOUNT_EVIDENCE=BLOCKED", output)

    def test_verifier_script_never_reads_secrets_or_constructs_authenticated_session(self):
        source = (ROOT / "scripts" / "verify_deriv_session.py").read_text(encoding="utf-8")
        self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", source)
        self.assertNotIn("get_optional_secret", source)
        self.assertNotIn("DerivSessionManager", source)
        self.assertNotIn("DerivAdapter", source)
        self.assertNotIn("DERIV_AUTH_TOKEN", source)
        self.assertNotIn("DERIV_PAT", source)

    def test_bearer_tokens_are_confined_to_one_live_gated_deployment_step(self):
        workflow = _workflow("self-hosted-runtime-deploy.yml")
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        deploy = _job(workflow, "deploy")
        self.assertIn("github.event_name == 'workflow_dispatch'", deploy.get("if", ""))
        self.assertIn("github.ref == 'refs/heads/main'", deploy.get("if", ""))
        self.assertEqual(deploy.get("environment"), "production")
        self.assertEqual(_secret_references(deploy.get("env", {})), [])
        token_steps = [
            step for step in _steps(deploy)
            if any(key in "\n".join(_strings(step.get("env", {}))) for key in DERIV_TOKEN_KEYS)
        ]
        self.assertEqual(len(token_steps), 1)
        self.assertEqual(token_steps[0].get("name"), "Provision LIVE runtime secrets to root-only host store")
        self.assertEqual(token_steps[0].get("if"), "inputs.deployment_mode == 'LIVE'")
        names = [step.get("name") for step in _steps(deploy)]
        self.assertLess(names.index("Verify source revision and deployment lock"),
                        names.index("Block LIVE deployment while Deriv read-only account scope is unavailable"))
        self.assertLess(names.index("Block LIVE deployment while Deriv read-only account scope is unavailable"),
                        names.index("Provision LIVE runtime secrets to root-only host store"))

    def test_deriv_configuration_uses_variables_or_boolean_presence(self):
        workflow = _workflow("secret-presence-report.yml")
        report = _job(workflow, "report")
        env = _step(report, "Report boolean-only production secret presence").get("env", {})
        for key in DERIV_CONFIG_KEYS:
            presence_key = key + "_PRESENT"
            self.assertIn(presence_key, env)
            self.assertTrue("vars." + key in env[presence_key] or "secrets." + key in env[presence_key], key)
        for key, value in env.items():
            if "secrets." in value:
                self.assertTrue(" != ''" in value or " == 'USD'" in value, (key, value))
        self.assertIn("DERIV_AUTH_TOKEN_PRESENT", env)
        self.assertIn("secrets.DERIV_AUTH_TOKEN", env["DERIV_AUTH_TOKEN_PRESENT"])
        self.assertIn("secrets.DERIV_PAT", env["DERIV_AUTH_TOKEN_PRESENT"])
        self.assertIn(" != ''", env["DERIV_AUTH_TOKEN_PRESENT"])
        self.assertNotIn("DERIV_AUTH_TOKEN", env)
        self.assertIn("vars.DERIV_AUTH_MODE", env["DERIV_AUTH_MODE"])
        self.assertIn("vars.DERIV_ENVIRONMENT", env["DERIV_ENVIRONMENT"])

    def test_session_alias_is_non_executing_and_credential_free(self):
        workflow = _workflow("deriv-session-verification.yml")
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        held = _job(workflow, "held")
        self.assertIn("github.event_name == 'workflow_dispatch'", held.get("if", ""))
        self.assertIn("github.ref == 'refs/heads/main'", held.get("if", ""))
        self.assertEqual(_secret_references(workflow), [])
        output = "\n".join(step.get("run", "") for step in _steps(held))
        self.assertIn("DERIV_SESSION_VERIFICATION=NOT_EXECUTED", output)
        self.assertIn("NEXT_STEP=MANUALLY_DISPATCH_DERIV_AUTH_EVIDENCE_ON_MAIN", output)

    def test_whatsapp_secrets_are_environment_protected_and_step_scoped(self):
        workflow = _workflow("aurelia-free-runtime.yml")
        self.assertNotIn("pull_request", workflow["on"])
        self.assertNotIn("pull_request_target", workflow["on"])
        runtime = _job(workflow, "runtime-probe")
        alert = _job(workflow, "whatsapp-alert-smoke")
        self.assertIn("github.event_name == 'workflow_dispatch'", alert.get("if", ""))
        self.assertIn("github.ref == 'refs/heads/main'", alert.get("if", ""))
        self.assertEqual(alert.get("environment"), "production")
        for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_API_KEY", "TWILIO_API_SECRET",
                    "TWILIO_WHATSAPP_FROM", "AURELIA_WHATSAPP_TO", "TWILIO_CONTENT_SID"):
            self.assertNotIn(key, runtime.get("env", {}))
        for key, value in alert.get("env", {}).items():
            if "secrets." in value:
                self.assertEqual(key, "TWILIO_CONFIGURED")
                self.assertIn(" != ''", value)
        send = _step(alert, "Send WhatsApp smoke alert")
        self.assertEqual(send.get("if"), "env.TWILIO_CONFIGURED == 'true'")
        for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_API_KEY", "TWILIO_API_SECRET",
                    "TWILIO_WHATSAPP_FROM", "AURELIA_WHATSAPP_TO", "TWILIO_CONTENT_SID"):
            self.assertIn("secrets.", send.get("env", {}).get(key, ""))

    def test_presence_report_is_manual_main_only_and_boolean_only(self):
        workflow = _workflow("secret-presence-report.yml")
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        report = _job(workflow, "report")
        self.assertEqual(report.get("environment"), "production")
        self.assertIn("github.event_name == 'workflow_dispatch'", report.get("if", ""))
        self.assertIn("github.ref == 'refs/heads/main'", report.get("if", ""))
        env = _step(report, "Report boolean-only production secret presence").get("env", {})
        for key, value in env.items():
            if "secrets." in value:
                self.assertTrue(" != ''" in value or " == 'USD'" in value, key)
        self.assertNotIn("DERIV_AUTH_TOKEN", env)
        self.assertNotIn("AURELIA_SSH_KEY", env)
        self.assertNotIn("AURELIA_ATTESTATION_SIGNING_KEY", env)

    def test_live_account_verification_blocks_before_trade_token_mapping(self):
        workflow = _workflow("self-hosted-runtime-deploy.yml")
        deploy = _job(workflow, "deploy")
        blocked = _step(deploy, "Block LIVE deployment while Deriv read-only account scope is unavailable")
        token_step = _step(deploy, "Provision LIVE runtime secrets to root-only host store")
        self.assertEqual(blocked.get("if"), "inputs.deployment_mode == 'LIVE'")
        self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", blocked.get("run", ""))
        self.assertEqual(token_step.get("if"), "inputs.deployment_mode == 'LIVE'")
        token_refs = [
            step for step in _steps(deploy)
            if any(key in "\n".join(_strings(step.get("env", {}))) for key in DERIV_TOKEN_KEYS)
        ]
        self.assertEqual(token_refs, [token_step])

    def test_verify_only_runtime_never_loads_retired_trade_scoped_store(self):
        source = (ROOT / "scripts" / "deploy" / "bootstrap_and_deploy.sh").read_text(encoding="utf-8")
        cleanup = source.index('sudo rm -f "$READONLY_SECRET_FILE"')
        self.assertLess(source.index('if [ ! -d "$RELEASE_DIR" ]'), cleanup)
        self.assertLess(source.index('test -f "$LOCK_FILE"'), cleanup)
        self.assertLess(source.index('case "$DEPLOYMENT_MODE" in'), cleanup)
        self.assertNotIn('ENV_FILES+=("$READONLY_SECRET_FILE")', source)
        self.assertNotIn('elif [ -f "$READONLY_SECRET_FILE" ]', source)
        self.assertNotIn('VERIFY_DERIV_AUTH="$AUTH_CONFIGURED"', source)
        self.assertNotIn("VERIFY_DERIV_AUTH=true", source)
        self.assertIn("VERIFY_DERIV_AUTH=false", source)
        self.assertNotIn("provision_deriv_readonly_secrets.py", source)

    def test_every_checkout_step_disables_persisted_github_credentials(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
            for job_name, job in workflow.get("jobs", {}).items():
                for step_number, step in enumerate(job.get("steps", []), start=1):
                    if str(step.get("uses", "")).startswith("actions/checkout@"):
                        self.assertEqual(
                            step.get("with", {}).get("persist-credentials"),
                            "false",
                            f"{path.name}:{job_name}:step{step_number} must disable persisted checkout credentials",
                        )

    def test_deployment_assurance_gate_requires_successful_main_push_for_exact_sha(self):
        workflow = _workflow("self-hosted-runtime-deploy.yml")
        deploy = _job(workflow, "deploy")
        code = _step(deploy, "Require green AURELIA Assurance for the exact commit").get("run", "")
        self.assertIn("headBranch", code)
        self.assertIn("headSha", code)
        self.assertIn('"main"', code)
        self.assertIn('"push"', code)
        self.assertIn("GITHUB_SHA", code)

    def test_public_runtime_has_no_deriv_credentials_or_account_settings(self):
        workflow = _workflow("aurelia-free-runtime.yml")
        runtime = _job(workflow, "runtime-probe")
        self.assertEqual(runtime.get("env", {}).get("AURELIA_VERIFY_DERIV_AUTH"), "false")
        output = "\n".join(step.get("run", "") for step in _steps(runtime))
        self.assertIn("python scripts/verify_deriv_public_transport.py", output)
        self.assertEqual(_secret_references(runtime), [])
        for key in DERIV_TOKEN_KEYS + DERIV_CONFIG_KEYS:
            self.assertNotIn(key, runtime.get("env", {}))

    def test_transaction_lifecycle_workflow_remains_held_without_secrets(self):
        workflow = _workflow("deriv-verify-only-lifecycle.yml")
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        held = _job(workflow, "held")
        self.assertIn("github.event_name == 'workflow_dispatch'", held.get("if", ""))
        self.assertIn("github.ref == 'refs/heads/main'", held.get("if", ""))
        self.assertEqual(_secret_references(workflow), [])
        output = "\n".join(step.get("run", "") for step in _steps(held))
        self.assertIn("VERIFY_ONLY_LIFECYCLE_REQUIRES_SEPARATE_NO_ORDER_ACTION_AUDIT", output)

    def test_self_hosted_deployment_is_manual_main_only_environment_protected_and_fail_closed(self):
        workflow = _workflow("self-hosted-runtime-deploy.yml")
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        deploy = _job(workflow, "deploy")
        self.assertIn("github.event_name == 'workflow_dispatch'", deploy.get("if", ""))
        self.assertIn("github.ref == 'refs/heads/main'", deploy.get("if", ""))
        self.assertEqual(deploy.get("environment"), "production")
        self.assertEqual(_secret_references(deploy.get("env", {})), [])
        self.assertEqual(workflow.get("permissions", {}).get("contents"), "read")
        self.assertEqual(workflow.get("permissions", {}).get("actions"), "read")
        lock_step = _step(deploy, "Verify source revision and deployment lock")
        self.assertIn("config/LIVE_LOCK.yaml", lock_step.get("run", ""))
        lock = (ROOT / "config" / "LIVE_LOCK.yaml").read_text(encoding="utf-8")
        self.assertIn("live_trading_enabled: false", lock)
        self.assertIn("FINAL_EXECUTION_AUTHORIZATION: false", lock)
        self.assertIn("LIVE_EXECUTION: BLOCKED", lock)
        self.assertIn("capital_plane_mode: VERIFY_ONLY", lock)


if __name__ == "__main__":
    unittest.main()
