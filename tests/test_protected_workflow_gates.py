"""Regression tests for GitHub Actions production-secret boundaries.

Credential-bearing jobs must stay on canonical main and require explicit owner
attestation that branch protection and production-environment reviewer gates
have been verified. These repository variables are intentionally unset by
default; do not set them merely to make CI green.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ".github/workflows/aurelia-assurance.yml",
    ".github/workflows/aurelia-free-runtime.yml",
    ".github/workflows/deriv-auth-evidence.yml",
    ".github/workflows/deriv-session-verification.yml",
    ".github/workflows/deriv-verify-only-lifecycle.yml",
    ".github/workflows/secret-presence-report.yml",
    ".github/workflows/self-hosted-runtime-deploy.yml",
)
REQUIRED_GATES = (
    "AURELIA_PRIVILEGED_CREDENTIAL_JOBS_ENABLED",
    "AURELIA_MAIN_BRANCH_PROTECTION_VERIFIED",
    "AURELIA_PRODUCTION_ENVIRONMENT_REVIEWER_GATE_VERIFIED",
)


def iter_jobs(workflow_text: str):
    """Yield (job_id, job block lines) without needing a YAML parser dependency."""
    lines = workflow_text.splitlines()
    try:
        jobs_index = next(i for i, line in enumerate(lines) if line.strip() == "jobs:")
    except StopIteration as exc:
        raise AssertionError("workflow has no jobs section") from exc

    starts = [
        i for i in range(jobs_index + 1, len(lines))
        if re.fullmatch(r"  [A-Za-z0-9_-]+:\s*", lines[i])
    ]
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        header = re.fullmatch(r"  ([A-Za-z0-9_-]+):\s*", lines[start])
        assert header is not None
        yield header.group(1), lines[start:end]


def uses_production_environment(block: list[str]) -> bool:
    for index, line in enumerate(block):
        if line.strip() == "environment: production":
            return True
        if line.strip() == "environment:" and index + 1 < len(block):
            if block[index + 1].strip() == "name: production":
                return True
    return False


def is_credential_bearing(block: list[str]) -> bool:
    return uses_production_environment(block) or any(
        "${{ secrets." in line for line in block
    )


def job_if_condition(block: list[str]) -> str:
    for line in block:
        if re.match(r"^    if:\s*", line):
            return line
    return ""


class ProtectedWorkflowGateTests(unittest.TestCase):
    def test_pull_request_assurance_job_has_no_production_environment_or_secret_expressions(self):
        path = ROOT / ".github/workflows/aurelia-assurance.yml"
        jobs = dict(iter_jobs(path.read_text(encoding="utf-8")))
        self.assertIn("assurance", jobs)
        block = jobs["assurance"]
        self.assertFalse(uses_production_environment(block))
        self.assertFalse(any("${{ secrets." in line for line in block))

    def test_every_credential_bearing_job_is_fail_closed_to_verified_main(self):
        for relative_path in WORKFLOWS:
            path = ROOT / relative_path
            self.assertTrue(path.is_file(), f"missing workflow: {relative_path}")
            text = path.read_text(encoding="utf-8")
            for job_id, block in iter_jobs(text):
                if not is_credential_bearing(block):
                    continue
                with self.subTest(workflow=relative_path, job=job_id):
                    condition = job_if_condition(block)
                    self.assertTrue(condition, "credential-bearing job has no job-level if gate")
                    self.assertIn("refs/heads/main", condition)
                    for gate in REQUIRED_GATES:
                        self.assertIn(gate, condition)
                    self.assertIn("== 'true'", condition)

    def test_protected_deriv_evidence_requires_main_push_and_all_gates(self):
        path = ROOT / ".github/workflows/aurelia-assurance.yml"
        jobs = dict(iter_jobs(path.read_text(encoding="utf-8")))
        self.assertIn("protected-deriv-evidence", jobs)
        condition = job_if_condition(jobs["protected-deriv-evidence"])
        self.assertIn("github.event_name == 'push'", condition)
        self.assertIn("refs/heads/main", condition)
        for gate in REQUIRED_GATES:
            self.assertIn(gate, condition)


if __name__ == "__main__":
    unittest.main()
