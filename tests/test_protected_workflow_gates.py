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
WORKFLOW_DIR = ROOT / ".github" / "workflows"
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
        workflow_paths = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
        self.assertTrue(workflow_paths, "no GitHub Actions workflow files found")
        for path in workflow_paths:
            relative_path = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            for job_id, block in iter_jobs(text):
                if not is_credential_bearing(block):
                    continue
                with self.subTest(workflow=relative_path, job=job_id):
                    if any("${{ secrets." in line for line in block):
                        self.assertTrue(
                            uses_production_environment(block),
                            "jobs that reference secrets must bind to the protected production environment",
                        )
                    condition = job_if_condition(block)
                    self.assertTrue(condition, "credential-bearing job has no job-level if gate")
                    self.assertIn("refs/heads/main", condition)
                    for gate in REQUIRED_GATES:
                        self.assertIn(f"{gate} == 'true'", condition)

    def test_assurance_jobs_set_explicit_fail_closed_execution_flags(self):
        path = ROOT / ".github/workflows/aurelia-assurance.yml"
        jobs = dict(iter_jobs(path.read_text(encoding="utf-8")))
        required = (
            'LIVE_EXECUTION: "BLOCKED"',
            'FINAL_EXECUTION_AUTHORIZATION: "false"',
            'AURELIA_VERIFY_ONLY: "true"',
            'AURELIA_ALLOW_LIVE_ORDERS: "false"',
        )
        for job_id in ("assurance", "protected-deriv-evidence"):
            with self.subTest(job=job_id):
                self.assertIn(job_id, jobs)
                for flag in required:
                    self.assertTrue(
                        any(flag in line for line in jobs[job_id]),
                        f"{job_id} missing explicit fail-closed flag: {flag}",
                    )

    def test_protected_deriv_evidence_requires_main_push_and_all_gates(self):
        path = ROOT / ".github/workflows/aurelia-assurance.yml"
        jobs = dict(iter_jobs(path.read_text(encoding="utf-8")))
        self.assertIn("protected-deriv-evidence", jobs)
        condition = job_if_condition(jobs["protected-deriv-evidence"])
        self.assertIn("github.event_name == 'push'", condition)
        self.assertIn("refs/heads/main", condition)
        for gate in REQUIRED_GATES:
            self.assertIn(f"{gate} == 'true'", condition)


    def test_every_external_github_action_uses_an_immutable_full_sha(self):
        workflow_paths = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
        self.assertTrue(workflow_paths, "no GitHub Actions workflow files found")
        uses_pattern = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
        sample = uses_pattern.match("      - uses: actions/checkout@" + "a" * 40)
        self.assertIsNotNone(sample, "action scanner must recognize a standard uses line")
        self.assertEqual(sample.group(1), "actions/checkout@" + "a" * 40)
        discovered_external_actions = 0
        for path in workflow_paths:
            relative_path = path.relative_to(ROOT).as_posix()
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                match = uses_pattern.match(line)
                if not match:
                    continue
                action_ref = match.group(1)
                if action_ref.startswith("./"):
                    continue
                discovered_external_actions += 1
                with self.subTest(workflow=relative_path, line=line_number, action=action_ref):
                    self.assertIn("@", action_ref, "external action must pin a ref")
                    revision = action_ref.rsplit("@", 1)[1]
                    self.assertRegex(
                        revision,
                        r"^[0-9a-f]{40}$",
                        "external actions must use a full immutable commit SHA, not a branch or release tag",
                    )
        self.assertGreater(discovered_external_actions, 0, "scanner must inspect at least one external action")

if __name__ == "__main__":
    unittest.main()
