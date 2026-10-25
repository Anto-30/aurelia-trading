import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SelfHostedDeploymentContractTests(unittest.TestCase):
    def test_provider_neutral_deployment_contract_exists(self):
        policy_path = ROOT / "config" / "deployment_policy.json"
        workflow_path = ROOT / ".github" / "workflows" / "self-hosted-runtime-deploy.yml"
        script_path = ROOT / "scripts" / "deploy" / "bootstrap_and_deploy.sh"
        watchdog_path = ROOT / "scripts" / "deploy" / "aurelia-watchdog.sh"

        self.assertTrue(policy_path.is_file(), "deployment policy missing")
        self.assertTrue(workflow_path.is_file(), "self-hosted workflow missing")
        self.assertTrue(script_path.is_file(), "self-hosted deployment script missing")
        self.assertTrue(watchdog_path.is_file(), "runtime watchdog missing")

        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertEqual(policy["primary_provider"], "self_hosted")
        self.assertTrue(policy["no_trial_dependency"])
        self.assertEqual(policy["capital_authority"], "LIVE_LOCK_only")

    def test_expired_railway_surface_is_removed(self):
        self.assertFalse((ROOT / ".github" / "workflows" / "railway-deploy.yml").exists())
        self.assertFalse((ROOT / "railway.toml").exists())

    def test_host_runtime_is_restartable_and_health_gated(self):
        source = (ROOT / "scripts" / "deploy" / "bootstrap_and_deploy.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("--restart unless-stopped", source)
        self.assertIn("http://127.0.0.1:8080/health", source)
        self.assertIn("DEPLOYED_SOURCE_SHA", source)
        self.assertIn("aurelia-runtime-watchdog.service", source)
        self.assertIn("if mode == \"VERIFY_ONLY\"", source)

    def test_assurance_uses_generic_deployment_script(self):
        workflow = (ROOT / ".github" / "workflows" / "aurelia-assurance.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("scripts/deploy/bootstrap_and_deploy.sh", workflow)
        self.assertNotIn("scripts/oci/bootstrap_and_deploy.sh", workflow)

    def test_live_secrets_remain_separate_but_workflow_only_has_verify_only_mode(self):
        workflow = (ROOT / ".github" / "workflows" / "self-hosted-runtime-deploy.yml").read_text(
            encoding="utf-8"
        )
        deploy = (ROOT / "scripts" / "deploy" / "bootstrap_and_deploy.sh").read_text(
            encoding="utf-8"
        )
        provisioner = (ROOT / "scripts" / "deploy" / "provision_runtime_secrets.py").read_text(
            encoding="utf-8"
        )
        readonly_provisioner = (
            ROOT / "scripts" / "deploy" / "provision_deriv_readonly_secrets.py"
        ).read_text(encoding="utf-8")

        # The deployment workflow cannot request or configure LIVE mode.
        self.assertIn(
            "if: github.ref == 'refs/heads/main' && inputs.confirm_verify_only == true",
            workflow,
        )
        self.assertIn('DEPLOYMENT_MODE: "VERIFY_ONLY"', workflow)
        self.assertNotIn("inputs.deployment_mode", workflow)
        self.assertNotIn("Provision LIVE runtime secrets", workflow)
        self.assertNotIn("secrets.DERIV_AUTH_TOKEN", workflow)
        self.assertIn("Configure strict SSH transport", workflow)

        # Keep host-side storage code independently fail-closed and separated.
        self.assertIn('LIVE_SECRET_FILE="$ENV_DIR/aurelia-live-secrets.env"', deploy)
        self.assertIn('READONLY_SECRET_FILE="$ENV_DIR/aurelia-deriv-readonly-secrets.env"', deploy)
        self.assertIn('if [ "$DEPLOYMENT_MODE" = "LIVE" ]; then', deploy)
        self.assertIn("os.fchmod(fd, 0o600)", provisioner)
        self.assertIn("os.replace(temporary, destination)", provisioner)
        self.assertIn('CAPITAL_AUTHORITY_GRANTED=false', provisioner)
        self.assertIn('CAPITAL_AUTHORITY_GRANTED=false', readonly_provisioner)

        presence_workflow = (
            ROOT / ".github" / "workflows" / "secret-presence-report.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("DERIV_EXPECTED_CURRENCY: ${{ secrets.DERIV_EXPECTED_CURRENCY }}", presence_workflow)
        self.assertIn("if: github.ref == 'refs/heads/main'", presence_workflow)
        self.assertNotIn("workflow_dispatch:", presence_workflow)

    def test_self_hosted_workflow_is_explicitly_verify_only_and_never_runs_live_release_gate(self):
        workflow = (
            ROOT / ".github" / "workflows" / "self-hosted-runtime-deploy.yml"
        ).read_text(encoding="utf-8")
        self.assertTrue((ROOT / "scripts" / "live_release_gate.py").is_file())
        self.assertTrue((ROOT / "scripts" / "verify_deriv_public_transport.py").is_file())
        self.assertIn("config/LIVE_LOCK.yaml", workflow)
        self.assertIn("b2cddd1efb0f25f35a6a08354290f805812bf34c", workflow)
        self.assertIn('FINAL_EXECUTION_AUTHORIZATION: "false"', workflow)
        self.assertIn('LIVE_EXECUTION: "BLOCKED"', workflow)
        self.assertIn("DEPLOYMENT_MODE=VERIFY_ONLY", workflow)
        self.assertNotIn("python scripts/live_release_gate.py", workflow)
        self.assertNotIn("if: inputs.deployment_mode == 'LIVE'", workflow)
        self.assertNotIn("deployment_mode:", workflow)
        self.assertNotIn("AURELIA_READINESS_OUT", workflow)
        self.assertNotIn("DERIV_PUBLIC_TRANSPORT_EVIDENCE_OUT", workflow)
        self.assertNotIn("artifacts/attestations", workflow)


if __name__ == "__main__":
    unittest.main()
