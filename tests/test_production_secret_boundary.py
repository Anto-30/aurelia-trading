from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

PRODUCTION_SECRET_JOBS = {
    "deriv-auth-evidence.yml": ("verify",),
    "deriv-session-verification.yml": ("verify",),
    "deriv-verify-only-lifecycle.yml": ("verify-only",),
    "self-hosted-runtime-deploy.yml": ("deploy",),
    "secret-presence-report.yml": ("report",),
    "aurelia-free-runtime.yml": (
        "authenticated-deriv-evidence",
        "deriv-lifecycle-verify-only",
        "whatsapp-alert-smoke",
    ),
}


def job_block(workflow: str, job_name: str) -> str:
    pattern = rf"(?ms)^  {re.escape(job_name)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)"
    match = re.search(pattern, workflow)
    if match is None:
        raise AssertionError(f"job not found: {job_name}")
    return match.group(1)


class ProductionSecretBoundaryTests(unittest.TestCase):
    def test_general_assurance_is_unprivileged_and_fail_closed(self) -> None:
        workflow = (WORKFLOWS / "aurelia-assurance.yml").read_text(encoding="utf-8")

        self.assertNotIn("environment: production", workflow)
        self.assertIsNone(re.search(r"\$\{\{\s*secrets\.", workflow))
        self.assertIn('FINAL_EXECUTION_AUTHORIZATION: "false"', workflow)
        self.assertIn('LIVE_EXECUTION: "BLOCKED"', workflow)
        self.assertIn('name: Run repository certification gate', workflow)
        self.assertIn('python scripts/live_release_gate.py', workflow)

    def test_every_production_or_secret_bearing_job_is_main_ref_guarded(self) -> None:
        for filename, job_names in PRODUCTION_SECRET_JOBS.items():
            workflow = (WORKFLOWS / filename).read_text(encoding="utf-8")
            for job_name in job_names:
                with self.subTest(workflow=filename, job=job_name):
                    block = job_block(workflow, job_name)
                    # Require the guard at the start of the job, before its
                    # environment declaration or any secret-bearing env.
                    first_lines = "\n".join(block.splitlines()[:5])
                    self.assertRegex(
                        first_lines,
                        r"^\s*if:\s*(?:\$\{\{\s*)?github\.ref\s*==\s*['\"]refs/heads/main['\"]",
                    )
                    self.assertTrue(
                        "environment: production" in block
                        or re.search(r"\$\{\{\s*secrets\.", block),
                        f"{filename}:{job_name} should remain in this explicit guard inventory",
                    )

    def test_sensitive_manual_workflows_remain_dispatch_only(self) -> None:
        lifecycle = (WORKFLOWS / "deriv-verify-only-lifecycle.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", lifecycle)
        self.assertNotIn("\n  pull_request:", lifecycle)
        deploy = (WORKFLOWS / "self-hosted-runtime-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", deploy)
        self.assertNotIn("\n  pull_request:", deploy)


if __name__ == "__main__":
    unittest.main()
