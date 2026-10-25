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
