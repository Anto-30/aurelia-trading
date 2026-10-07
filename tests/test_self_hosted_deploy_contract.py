import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SelfHostedDeploymentContractTests(unittest.TestCase):
    def test_provider_neutral_deployment_contract_exists(self):
        policy_path = ROOT / "config" / "deployment_policy.json"
        workflow_path = ROOT / ".github" / "workflows" / "self-hosted-runtime-deploy.yml"
        script_path = ROOT / "scripts" / "deploy" / "bootstrap_and_deploy.sh"

        self.assertTrue(policy_path.is_file(), "deployment policy missing")
        self.assertTrue(workflow_path.is_file(), "self-hosted workflow missing")
        self.assertTrue(script_path.is_file(), "self-hosted deployment script missing")

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

    def test_assurance_uses_generic_deployment_script(self):
        workflow = (ROOT / ".github" / "workflows" / "aurelia-assurance.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("scripts/deploy/bootstrap_and_deploy.sh", workflow)
        self.assertNotIn("scripts/oci/bootstrap_and_deploy.sh", workflow)


if __name__ == "__main__":
    unittest.main()
