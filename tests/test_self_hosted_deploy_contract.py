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

    def test_live_secrets_are_separate_root_only_and_not_loaded_in_verify_only(self):
        workflow = (ROOT / ".github" / "workflows" / "self-hosted-runtime-deploy.yml").read_text(
            encoding="utf-8"
        )
        deploy = (ROOT / "scripts" / "deploy" / "bootstrap_and_deploy.sh").read_text(
            encoding="utf-8"
        )
        provisioner = (ROOT / "scripts" / "deploy" / "provision_runtime_secrets.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("Provision LIVE runtime secrets to root-only host store", workflow)
        self.assertIn("sudo -n python3 /opt/aurelia/releases/$GITHUB_SHA/scripts/deploy/provision_runtime_secrets.py", workflow)
        self.assertIn("artifacts/attestations", workflow)
        self.assertIn('LIVE_SECRET_FILE="$ENV_DIR/aurelia-live-secrets.env"', deploy)
        self.assertIn('SECRET_ENV_ARGS+=(--env-file "$LIVE_SECRET_FILE")', deploy)
        self.assertIn('if [ "$DEPLOYMENT_MODE" = "LIVE" ]; then', deploy)
        self.assertIn("os.fchmod(fd, 0o600)", provisioner)
        self.assertIn("os.replace(temporary, destination)", provisioner)
        self.assertIn('CAPITAL_AUTHORITY_GRANTED=false', provisioner)

    def test_live_deployment_requires_release_gate(self):
        workflow = (ROOT / ".github" / "workflows" / "self-hosted-runtime-deploy.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("python scripts/live_release_gate.py", workflow)
        self.assertIn("if: inputs.deployment_mode == 'LIVE'", workflow)


if __name__ == "__main__":
    unittest.main()
