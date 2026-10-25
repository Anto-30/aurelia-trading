from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_LOCK_BLOB_SHA = "b2cddd1efb0f25f35a6a08354290f805812bf34c"
LOCK_PATH = ROOT / "config" / "LIVE_LOCK.yaml"
ASSURANCE_PATH = ROOT / ".github" / "workflows" / "aurelia-assurance.yml"
PROTECTED_PATH = ROOT / ".github" / "workflows" / "aurelia-protected-deriv-verification.yml"


def git_blob_sha(raw: bytes) -> str:
    header = b"blob " + str(len(raw)).encode("ascii") + b"\0"
    return hashlib.sha1(header + raw).hexdigest()


class CISecurityBoundaryTests(unittest.TestCase):
    def test_canonical_lock_is_exact_and_fail_closed(self):
        raw = LOCK_PATH.read_bytes()
        self.assertEqual(git_blob_sha(raw), EXPECTED_LOCK_BLOB_SHA)
        lock = raw.decode("utf-8")
        for required in (
            "live_trading_enabled: false",
            "FINAL_EXECUTION_AUTHORIZATION: false",
            "LIVE_EXECUTION: BLOCKED",
            "capital_plane_mode: VERIFY_ONLY",
            "research_capital_authority: false",
            "external_repositories_capital_forbidden: true",
            "blind_resubmission: false",
            "kill_switch_independent: true",
        ):
            self.assertIn(required, lock)

    def test_routine_assurance_is_secret_free_and_checkout_is_read_only(self):
        workflow = ASSURANCE_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(workflow, r"\$\{\{[^}]*\bsecrets\s*\.")
        self.assertNotRegex(workflow, r"(?m)^\s*environment:\s*production\s*$")
        self.assertIn('FINAL_EXECUTION_AUTHORIZATION: "false"', workflow)
        self.assertIn('LIVE_EXECUTION: "BLOCKED"', workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertRegex(
            workflow,
            r"(?m)^\s*- uses: [^\s@]+@[0-9a-f]{40}(?:\s+#.*)?$",
        )

    def test_public_runtime_worker_is_secret_free_and_main_gated(self):
        workflow = (
            ROOT / ".github" / "workflows" / "aurelia-free-runtime.yml"
        ).read_text(encoding="utf-8")
        self.assertNotRegex(workflow, r"\\$\\{\\{[^}]*\\bsecrets\\s*\\.")
        self.assertNotRegex(workflow, r"(?m)^\\s*environment:\\s*production\\s*$")
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)
        self.assertIn('AURELIA_VERIFY_DERIV_AUTH: "false"', workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("authenticated-deriv-evidence:", workflow)
        self.assertNotIn("deriv-lifecycle-verify-only:", workflow)
        self.assertNotIn("whatsapp-alert-smoke:", workflow)
        self.assertRegex(
            workflow,
            r"(?m)^\\s*- uses: [^\\s@]+@[0-9a-f]{40}(?:\\s+#.*)?$",
        )

    def test_secret_presence_report_gates_main_and_scopes_secrets_to_report_step(self):
        path = ROOT / ".github" / "workflows" / "secret-presence-report.yml"
        workflow = path.read_text(encoding="utf-8")
        secret_expression = r"\\$\\{\\{[^}]*\\bsecrets\\s*\\."
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)
        self.assertRegex(workflow, r"(?m)^\\s*environment:\\s*production\\s*$")
        self.assertIn("persist-credentials: false", workflow)
        before_steps = workflow.split("    steps:", 1)[0]
        self.assertNotRegex(before_steps, secret_expression)
        report_section = workflow.split(
            "      - name: Run secret presence report", 1
        )[1].split("      - name: Install secret-report test dependency", 1)[0]
        self.assertRegex(report_section, secret_expression)
        after_report = workflow.split(
            "      - name: Install secret-report test dependency", 1
        )[1]
        self.assertNotRegex(after_report, secret_expression)

    def test_self_hosted_deployment_is_explicit_verify_only_and_main_gated(self):
        workflow = (
            ROOT / ".github" / "workflows" / "self-hosted-runtime-deploy.yml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "if: github.ref == 'refs/heads/main' && inputs.confirm_verify_only == true",
            workflow,
        )
        self.assertIn("confirm_verify_only:", workflow)
        self.assertIn("type: boolean", workflow)
        self.assertIn("default: false", workflow)
        self.assertIn('DEPLOYMENT_MODE: "VERIFY_ONLY"', workflow)
        self.assertIn(EXPECTED_LOCK_BLOB_SHA, workflow)
        self.assertIn('FINAL_EXECUTION_AUTHORIZATION: "false"', workflow)
        self.assertIn('LIVE_EXECUTION: "BLOCKED"', workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("inputs.deployment_mode", workflow)
        self.assertNotIn("deployment_mode:", workflow)
        self.assertNotIn("          - LIVE", workflow)
        self.assertNotIn("if: inputs.deployment_mode == 'LIVE'", workflow)
        self.assertNotRegex(
            workflow, r"\\$\\{\\{[^}]*\\bsecrets\\s*\\.\\s*DERIV_"
        )
        sections = re.split(r"(?m)^      - name: ", workflow)
        secret_sections = [section for section in sections if "secrets." in section]
        self.assertEqual(len(secret_sections), 1)
        self.assertIn("Configure strict SSH transport", secret_sections[0])
        self.assertNotIn(
            "secrets.",
            workflow.split("      - name: Package exact source commit", 1)[1],
        )

    def test_legacy_deriv_workflows_are_retired_and_have_no_secret_boundary(self):
        legacy_paths = (
            ".github/workflows/deriv-auth-evidence.yml",
            ".github/workflows/deriv-session-verification.yml",
            ".github/workflows/deriv-verify-only-lifecycle.yml",
        )
        for relative_path in legacy_paths:
            with self.subTest(path=relative_path):
                workflow = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("LEGACY_DERIV_WORKFLOW=RETIRED", workflow)
                self.assertIn("exit 1", workflow)
                self.assertIn("permissions: {}", workflow)
                self.assertNotRegex(
                    workflow, r"\\$\\{\\{[^}]*\\bsecrets\\s*\\."
                )
                self.assertNotRegex(
                    workflow, r"(?m)^\\s*environment:\\s*production\\s*$"
                )
                self.assertNotIn("schedule:", workflow)
                self.assertNotIn("actions/checkout@", workflow)
                self.assertNotIn("python scripts/verify_deriv_", workflow)

    def test_authenticated_verifier_requires_manual_main_read_only_gate(self):
        workflow = PROTECTED_PATH.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("type: boolean", workflow)
        self.assertIn("default: false", workflow)
        self.assertIn("github.ref == 'refs/heads/main' && inputs.confirm_read_only == true", workflow)
        self.assertRegex(workflow, r"(?m)^\s*environment:\s*production\s*$")
        self.assertIn(EXPECTED_LOCK_BLOB_SHA, workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn('FINAL_EXECUTION_AUTHORIZATION: "false"', workflow)
        self.assertIn('LIVE_EXECUTION: "BLOCKED"', workflow)

    def test_protected_workflow_credentials_are_step_scoped(self):
        workflow = PROTECTED_PATH.read_text(encoding="utf-8")
        steps = re.split(r"(?m)^      - name: ", workflow)
        secret_sections = [section for section in steps if "secrets." in section]
        self.assertEqual(len(secret_sections), 2)
        for section in secret_sections:
            self.assertTrue(
                "Verify authenticated account binding and balance (read-only)" in section
                or "Verify broker account statement and portfolio (read-only)" in section
            )
        self.assertNotIn("secrets.", workflow.split("      - name: Create privacy-minimised read-only attestation", 1)[-1])


if __name__ == "__main__":
    unittest.main()
