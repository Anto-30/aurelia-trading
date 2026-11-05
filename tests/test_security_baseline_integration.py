from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FORBIDDEN_DERIV_SECRET_NAMES = (
    "DERIV_AUTH_TOKEN",
    "DERIV_PAT",
    "DERIV_OAUTH_ACCESS_TOKEN",
    "DERIV_OAUTH_REFRESH_TOKEN",
    "DERIV_REFRESH_TOKEN",
    "DERIV_APP_ID",
    "DERIV_EXPECTED_LOGINID",
    "DERIV_AUTHORIZED_ACCOUNT_ID",
)


def load_workflow(filename: str) -> dict:
    path = WORKFLOWS / filename
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def assert_no_deriv_credentials(test: unittest.TestCase, value: object) -> None:
    rendered = yaml.safe_dump(value, sort_keys=True)
    for name in FORBIDDEN_DERIV_SECRET_NAMES:
        test.assertNotIn(
            f"secrets.{name}",
            rendered,
            msg=f"{name} must not be referenced by this workflow",
        )
        test.assertNotIn(
            f"${{{{ secrets.{name}",
            rendered,
            msg=f"{name} must not be injected into this workflow",
        )


class SecurityBaselineIntegrationTests(unittest.TestCase):
    def test_general_assurance_has_no_production_environment_or_deriv_secrets(self):
        workflow = load_workflow("aurelia-assurance.yml")
        job = workflow["jobs"]["assurance"]

        self.assertNotEqual(job.get("environment"), "production")
        self.assertEqual(workflow.get("permissions", {}).get("contents"), "read")
        assert_no_deriv_credentials(self, job)

        for step in job.get("steps", []):
            assert_no_deriv_credentials(self, step.get("env", {}))

    def test_public_auth_evidence_workflow_never_receives_account_credentials(self):
        workflow = load_workflow("deriv-auth-evidence.yml")
        jobs = workflow.get("jobs", {})
        self.assertTrue(jobs)

        for job in jobs.values():
            self.assertNotEqual(job.get("environment"), "production")
            assert_no_deriv_credentials(self, job)
            for step in job.get("steps", []):
                assert_no_deriv_credentials(self, step.get("env", {}))

    def test_canonical_live_lock_remains_fail_closed(self):
        lock = yaml.safe_load(
            (ROOT / "config" / "LIVE_LOCK.yaml").read_text(encoding="utf-8")
        )

        self.assertIs(lock["live_trading_enabled"], False)
        self.assertIs(lock["FINAL_EXECUTION_AUTHORIZATION"], False)
        self.assertEqual(lock["LIVE_EXECUTION"], "BLOCKED")
        self.assertEqual(lock["capital_plane_mode"], "VERIFY_ONLY")
        self.assertIs(lock["research_capital_authority"], False)
        self.assertIs(lock["external_repositories_capital_forbidden"], True)
        self.assertIs(lock["blind_resubmission"], False)
        self.assertIs(lock["kill_switch_independent"], True)


if __name__ == "__main__":
    unittest.main()
