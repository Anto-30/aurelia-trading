from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from runtime.security.deriv_auth_gate import ACCOUNT_CREDENTIAL_ENV_NAMES
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
        self.assertIn("DERIV_ACCOUNT_INPUT_BINDING", {item[2] for item in findings})

    def test_rejects_bracket_notation_deriv_secret_reference(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manual.yml").write_text(
                "jobs:\n  verify:\n    env:\n"
                "      DERIV_AUTH_TOKEN: ${{ secrets['DERIV_PAT'] }}\n",
                encoding="utf-8",
            )
            _count, findings = audit_workflows(root)
        self.assertIn("DERIV_SECRET_REFERENCE", {item[2] for item in findings})

    def test_rejects_dynamic_secret_lookup_that_mentions_deriv(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dynamic.yml").write_text(
                "jobs:\n  verify:\n    env:\n"
                "      TOKEN: ${{ secrets[vars.DERIV_SECRET_NAME] }}\n",
                encoding="utf-8",
            )
            _count, findings = audit_workflows(root)
        self.assertIn("DERIV_SECRET_REFERENCE", {item[2] for item in findings})

    def test_rejects_every_account_plane_environment_key(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            content = "jobs:\n  verify:\n    env:\n"
            content += "".join(f'      {name}: ""\n' for name in ACCOUNT_CREDENTIAL_ENV_NAMES)
            (root / "account-inputs.yml").write_text(content, encoding="utf-8")
            _count, findings = audit_workflows(root)
        self.assertIn("DERIV_ACCOUNT_INPUT_BINDING", {item[2] for item in findings})

    def test_rejects_inline_account_input_mapping(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "inline.yml").write_text(
                'jobs:\n  verify:\n    env: { DERIV_APP_ID: "public-app" }\n',
                encoding="utf-8",
            )
            _count, findings = audit_workflows(root)
        self.assertIn("DERIV_ACCOUNT_INPUT_BINDING", {item[2] for item in findings})

    def test_ignores_commented_out_examples(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "comments.yml").write_text(
                "# DERIV_PAT: ${{ secrets.DERIV_PAT }}\n"
                'env:\n  ACCOUNT_DERIV_AUTH_MODE: "none"\n',
                encoding="utf-8",
            )
            _count, findings = audit_workflows(root)
        self.assertEqual(findings, [])

    def test_allows_explicit_blocked_account_plane_without_credentials(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "safe.yml").write_text(
                'env:\n'
                '  ACCOUNT_DERIV_AUTH_MODE: "none"\n'
                '  DERIV_ACCOUNT_EVIDENCE: "BLOCKED"\n'
                '  DERIV_ACCOUNT_BLOCK_REASON: "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"\n',
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
