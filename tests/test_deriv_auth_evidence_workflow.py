from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ROOT / ".github" / "workflows" / "aurelia-assurance.yml",
    ROOT / ".github" / "workflows" / "deriv-auth-evidence.yml",
    ROOT / ".github" / "workflows" / "deriv-verify-only-lifecycle.yml",
)
SAFE_AUTH_MODE_BINDING = "${{ vars.DERIV_AUTH_MODE == 'oauth' && 'oauth' || 'invalid' }}"


class DerivAuthWorkflowContractTests(unittest.TestCase):
    def test_all_deriv_workflows_expose_only_oauth_or_invalid(self):
        for path in WORKFLOWS:
            workflow = path.read_text(encoding="utf-8")
            bindings = [
                line.strip() for line in workflow.splitlines()
                if line.strip().startswith("DERIV_AUTH_MODE:")
            ]
            self.assertEqual(bindings, [f"DERIV_AUTH_MODE: {SAFE_AUTH_MODE_BINDING}"], path.name)
            self.assertNotIn("vars.DERIV_AUTH_MODE || 'pat'", workflow)
            self.assertNotIn("secrets.DERIV_AUTH_MODE", workflow)

    def test_assurance_auth_configuration_requires_explicit_oauth(self):
        workflow = WORKFLOWS[0].read_text(encoding="utf-8")
        self.assertIn("vars.DERIV_AUTH_MODE == 'oauth'", workflow)
        self.assertNotIn("DERIV_APP_ID", workflow)

    def test_scheduled_deriv_verifier_uses_oauth_token_only(self):
        workflow = WORKFLOWS[1].read_text(encoding="utf-8")
        self.assertIn("DERIV_AUTH_TOKEN: ${{ secrets.DERIV_AUTH_TOKEN }}", workflow)
        self.assertNotIn("secrets.DERIV_PAT", workflow)
        self.assertNotIn("DERIV_APP_ID", workflow)
        self.assertIn("test \"$auth_mode\" = \"oauth\"", workflow)
        self.assertIn("DERIV_EXPECTED_CURRENCY: ${{ secrets.DERIV_EXPECTED_CURRENCY }}", workflow)

    def test_scheduled_workflow_generates_read_only_broker_account_evidence(self):
        workflow = WORKFLOWS[1].read_text(encoding="utf-8")
        self.assertIn("python scripts/verify_deriv_broker_evidence.py", workflow)
        self.assertIn("artifacts/deriv_broker_account_evidence.json", workflow)

    def test_scheduled_deriv_verifier_keeps_capital_authority_blocked(self):
        workflow = WORKFLOWS[1].read_text(encoding="utf-8")
        self.assertIn('FINAL_EXECUTION_AUTHORIZATION: "false"', workflow)
        self.assertIn('LIVE_EXECUTION: "BLOCKED"', workflow)
        self.assertIn('echo "DERIV_ORDERS_SUBMITTED=0"', workflow)

    def test_lifecycle_workflow_requires_oauth_and_verify_only(self):
        workflow = WORKFLOWS[2].read_text(encoding="utf-8")
        self.assertIn('DERIV_LIFECYCLE_MODE: "VERIFY_ONLY"', workflow)
        self.assertIn('test "$auth_mode" = "oauth"', workflow)
        self.assertNotIn("secrets.DERIV_PAT", workflow)
        self.assertNotIn("DERIV_APP_ID", workflow)


if __name__ == "__main__":
    unittest.main()
