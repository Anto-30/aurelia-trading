from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.audit_deriv_workflow_credentials import audit_workflows


class DerivWorkflowCredentialAuditTests(unittest.TestCase):
    def test_rejects_scheduled_secret_injection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scheduled.yml").write_text(
                "on:\n  schedule:\n    - cron: '*/15 * * * *'\njobs:\n"
                "  verify:\n    env:\n"
                "      DERIV_AUTH_TOKEN: ${{ secrets.DERIV_PAT }}\n",
                encoding="utf-8",
            )
            count, findings = audit_workflows(root)
        self.assertEqual(count, 1)
        self.assertIn("DERIV_SECRET_REFERENCE", {item[2] for item in findings})
        self.assertIn("DERIV_CREDENTIAL_ENV_BINDING", {item[2] for item in findings})

    def test_rejects_manual_oauth_secret_injection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manual.yml").write_text(
                "on:\n  workflow_dispatch:\njobs:\n"
                "  verify:\n    env:\n"
                "      DERIV_OAUTH_ACCESS_TOKEN: ${{ secrets.DERIV_OAUTH_ACCESS_TOKEN }}\n",
                encoding="utf-8",
            )
            _count, findings = audit_workflows(root)
        self.assertTrue(findings)
        self.assertTrue(all(item[0] == "manual.yml" for item in findings))

    def test_rejects_credential_environment_binding_without_secret_expression(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "binding.yml").write_text(
                "jobs:\n  verify:\n    env:\n      DERIV_PAT: \"\"\n",
                encoding="utf-8",
            )
            _count, findings = audit_workflows(root)
        self.assertIn("DERIV_CREDENTIAL_ENV_BINDING", {item[2] for item in findings})

    def test_allows_explicit_blocked_account_plane_without_credentials(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "safe.yml").write_text(
                "env:\n"
                "  ACCOUNT_DERIV_AUTH_MODE: \"oauth\"\n"
                "  DERIV_ACCOUNT_EVIDENCE: \"BLOCKED\"\n"
                "  DERIV_ACCOUNT_BLOCK_REASON: \"DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE\"\n",
                encoding="utf-8",
            )
            count, findings = audit_workflows(root)
        self.assertEqual(count, 1)
        self.assertEqual(findings, [])

    def test_missing_workflow_directory_fails_closed(self):
        with TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            count, findings = audit_workflows(missing)
        self.assertEqual(count, 0)
        self.assertEqual(findings[0][2], "WORKFLOW_DIRECTORY_MISSING")


if __name__ == "__main__":
    unittest.main()
