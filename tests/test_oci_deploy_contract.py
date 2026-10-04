import unittest
from pathlib import Path


class OciDeployContractTest(unittest.TestCase):
    SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "oci" / "bootstrap_and_deploy.sh"

    def test_verify_only_auth_probe_is_conditional_on_configured_credentials(self):
        source = self.SCRIPT.read_text(encoding="utf-8")
        self.assertIn("AUTH_CONFIGURED=false", source)
        self.assertIn('VERIFY_DERIV_AUTH="$AUTH_CONFIGURED"', source)

    def test_live_mode_still_requires_authenticated_deriv_configuration(self):
        source = self.SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            'echo "OCI_RUNTIME_BLOCKED=MISSING_DERIV_CONFIG:${key}"',
            source,
        )
        self.assertIn('if [ "$DEPLOYMENT_MODE" = "LIVE" ]; then', source)


if __name__ == "__main__":
    unittest.main()
