from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


# Job-level conditions are deliberate defense in depth. Environment reviewers
# must still approve protected jobs; these assertions prevent a future workflow
# edit from accidentally exposing production credentials to a non-main ref.
PROTECTED_JOBS = {
    ".github/workflows/aurelia-assurance.yml": {
        "deriv-verify-only": "if: github.event_name == 'push' && github.ref == 'refs/heads/main'",
    },
    ".github/workflows/aurelia-free-runtime.yml": {
        "authenticated-deriv-evidence": "if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}",
        "deriv-lifecycle-verify-only": "if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}",
    },
    ".github/workflows/deriv-auth-evidence.yml": {
        "verify": "if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}",
    },
    ".github/workflows/deriv-session-verification.yml": {
        "verify": "if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}",
    },
    ".github/workflows/deriv-verify-only-lifecycle.yml": {
        "verify-only": "if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}",
    },
    ".github/workflows/self-hosted-runtime-deploy.yml": {
        "deploy": "if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}",
    },
    ".github/workflows/secret-presence-report.yml": {
        "report": "if: ${{ github.ref == 'refs/heads/main' }}",
    },
}


def _job_block(path: str, job_name: str) -> str:
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    header = f"  {job_name}:"
    try:
        start = lines.index(header)
    except ValueError as exc:
        raise AssertionError(f"job {job_name!r} not found in {path}") from exc

    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        # Normalize trailing whitespace, then stop only at an un-commented,
        # two-space-indented YAML key (the next GitHub Actions job).
        if indent == 2 and not stripped.startswith("#") and re.fullmatch(r"[A-Za-z0-9_-]+:", stripped):
            end = index
            break
    return "\n".join(lines[start:end])


class ProtectedWorkflowSourceGuardTests(unittest.TestCase):
    def test_each_credential_bearing_job_is_guarded_to_main(self):
        for path, jobs in PROTECTED_JOBS.items():
            for job_name, guard in jobs.items():
                with self.subTest(path=path, job=job_name):
                    block = _job_block(path, job_name)
                    self.assertIn(guard, block)
                    secret_binding_index = block.find("${{ secrets.")
                    self.assertGreaterEqual(
                        secret_binding_index,
                        0,
                        msg=f"expected an explicit secret binding in {path}:{job_name}",
                    )
                    self.assertLess(
                        block.index(guard),
                        secret_binding_index,
                        msg=f"source-ref guard must precede secret bindings in {path}:{job_name}",
                    )
                    self.assertTrue(
                        "environment: production" in block
                        or re.search(r"environment:\n\s+name: production", block),
                        msg=f"expected protected production environment on {path}:{job_name}",
                    )

    def test_whatsapp_smoke_is_main_only_without_assuming_production_environment(self):
        block = _job_block(".github/workflows/aurelia-free-runtime.yml", "whatsapp-alert-smoke")
        self.assertIn(
            "if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}",
            block,
        )

    def test_general_assurance_job_has_no_production_environment_or_secrets(self):
        block = _job_block(".github/workflows/aurelia-assurance.yml", "assurance")
        self.assertNotIn("environment: production", block)
        self.assertNotIn("secrets.", block)

    def test_periodic_public_runtime_probe_does_not_run_full_test_suites(self):
        block = _job_block(".github/workflows/aurelia-free-runtime.yml", "runtime-probe")
        runtime_tests = block.index("- name: Run runtime tests")
        assurance_tests = block.index("- name: Run assurance tests")
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}", block[runtime_tests:])
        self.assertIn("if: ${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}", block[assurance_tests:])

    def test_deriv_public_and_research_workflows_remain_secret_free(self):
        for path in (
            ".github/workflows/r100-prospective-oos.yml",
            ".github/workflows/external-repo-sync.yml",
        ):
            with self.subTest(path=path):
                workflow = (ROOT / path).read_text(encoding="utf-8")
                self.assertNotIn("secrets.", workflow)


if __name__ == "__main__":
    unittest.main()
