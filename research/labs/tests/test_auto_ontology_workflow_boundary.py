"""Regression tests for the research-only CI / protected Deriv CI split."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "aurelia-assurance.yml"
RESEARCH_WORKFLOW = ROOT / ".github" / "workflows" / "aurelia-research-ci.yml"


def job_blocks(text):
    lines = text.splitlines()
    jobs_index = next(i for i, line in enumerate(lines) if line.strip() == "jobs:")
    starts = [
        i for i in range(jobs_index + 1, len(lines))
        if re.fullmatch(r"  [A-Za-z0-9_-]+:\s*", lines[i])
    ]
    result = {}
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        name = lines[start].strip().split(":", 1)[0]
        result[name] = "\n".join(lines[start:end])
    return result


class ResearchCiBoundaryTests(unittest.TestCase):
    def test_general_assurance_has_no_production_environment_or_secrets(self):
        jobs = job_blocks(WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn("assurance", jobs)
        block = jobs["assurance"]
        self.assertNotIn("environment: production", block)
        self.assertNotIn("${{ secrets.", block)

    def test_protected_deriv_job_is_main_push_and_explicitly_gated(self):
        jobs = job_blocks(WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn("protected-deriv-evidence", jobs)
        block = jobs["protected-deriv-evidence"]
        self.assertIn("github.event_name == 'push'", block)
        self.assertIn("refs/heads/main", block)
        self.assertIn("AURELIA_PRIVILEGED_CREDENTIAL_JOBS_ENABLED == 'true'", block)
        self.assertIn("AURELIA_MAIN_BRANCH_PROTECTION_VERIFIED == 'true'", block)
        self.assertIn("AURELIA_PRODUCTION_ENVIRONMENT_REVIEWER_GATE_VERIFIED == 'true'", block)
        self.assertIn("environment: production", block)

    def test_research_ci_is_secret_free_and_has_no_production_environment(self):
        text = RESEARCH_WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("${{ secrets.", text)
        self.assertNotIn("environment: production", text)
        self.assertIn("permissions:", text)
        self.assertIn("contents: read", text)
        self.assertIn("pull_request:", text)


if __name__ == "__main__":
    unittest.main()
