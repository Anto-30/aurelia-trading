from __future__ import annotations

import io
import json
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.deploy import provision_runtime_secrets as provisioner


def payload(mode: str = "pat") -> dict[str, str]:
    return {
        "DERIV_AUTH_TOKEN": "SENSITIVE_TOKEN_DO_NOT_PRINT",
        "DERIV_APP_ID": "12345" if mode == "pat" else "",
        "DERIV_EXPECTED_LOGINID": "CR123456",
        "DERIV_EXPECTED_CURRENCY": "USD",
        "DERIV_ENVIRONMENT": "real",
        "DERIV_AUTH_MODE": mode,
        "AURELIA_ATTESTATION_SIGNING_KEY": "SENSITIVE_SIGNING_KEY_DO_NOT_PRINT",
        "AURELIA_RUNTIME_ID": "aurelia-production-worker",
    }


class RuntimeSecretProvisionerTests(unittest.TestCase):
    def test_pat_creates_private_file_without_printing_values(self):
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "private" / "aurelia-live-secrets.env"
            out, err = io.StringIO(), io.StringIO()
            with patch.object(provisioner, "LIVE_SECRET_FILE", destination), \
                 patch("sys.stdin", io.StringIO(json.dumps(payload()))), \
                 redirect_stdout(out), redirect_stderr(err):
                status = provisioner.main()

            self.assertEqual(status, 0)
            self.assertIn("AURELIA_RUNTIME_SECRET_PROVISIONING=COMPLETE", out.getvalue())
            self.assertIn("SECRET_VALUES_PRINTED=false", out.getvalue())
            self.assertIn("SECRET_FILE_PERMISSIONS=0600", out.getvalue())
            self.assertIn("CAPITAL_AUTHORITY_GRANTED=false", out.getvalue())
            self.assertNotIn("SENSITIVE_TOKEN_DO_NOT_PRINT", out.getvalue() + err.getvalue())
            self.assertNotIn("SENSITIVE_SIGNING_KEY_DO_NOT_PRINT", out.getvalue() + err.getvalue())

            mode = stat.S_IMODE(destination.stat().st_mode)
            self.assertEqual(mode, 0o600)
            text = destination.read_text(encoding="utf-8")
            self.assertIn("DERIV_AUTH_TOKEN=SENSITIVE_TOKEN_DO_NOT_PRINT\n", text)
            self.assertIn("DERIV_APP_ID=12345\n", text)
            self.assertIn("DERIV_ENVIRONMENT=real\n", text)
            self.assertIn("AURELIA_RUNTIME_ID=aurelia-production-worker\n", text)

    def test_oauth_does_not_require_pat_app_id(self):
        content = provisioner.build_env_text(payload("oauth"))
        self.assertIn("DERIV_AUTH_MODE=oauth\n", content)
        self.assertNotIn("DERIV_APP_ID=", content)
        self.assertIn("DERIV_EXPECTED_LOGINID=CR123456\n", content)

    def test_rejects_non_real_environment(self):
        value = payload()
        value["DERIV_ENVIRONMENT"] = "demo"
        with self.assertRaisesRegex(
            provisioner.RuntimeSecretProvisioningError,
            "LIVE_RUNTIME_REQUIRES_REAL_ACCOUNT",
        ):
            provisioner.build_env_text(value)

    def test_rejects_pat_without_app_id(self):
        value = payload()
        value["DERIV_APP_ID"] = ""
        with self.assertRaisesRegex(
            provisioner.RuntimeSecretProvisioningError,
            "DERIV_APP_ID_REQUIRED_FOR_PAT",
        ):
            provisioner.build_env_text(value)

    def test_rejects_newlines_and_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "aurelia-live-secrets.env"
            provisioner.provision(payload(), destination)
            previous = destination.read_bytes()

            malformed = payload()
            malformed["DERIV_AUTH_TOKEN"] = "token\nINJECTED_VARIABLE=true"
            with self.assertRaisesRegex(
                provisioner.RuntimeSecretProvisioningError,
                "MULTILINE_VALUE_REJECTED_DERIV_AUTH_TOKEN",
            ):
                provisioner.provision(malformed, destination)

            self.assertEqual(destination.read_bytes(), previous)
            self.assertFalse(list(Path(td).glob("*.tmp")))

    def test_invalid_json_is_reported_without_input_echo(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(provisioner, "LIVE_SECRET_FILE", Path("/not-used")), \
             patch("sys.stdin", io.StringIO("{invalid")), \
             redirect_stdout(out), redirect_stderr(err):
            status = provisioner.main()

        self.assertEqual(status, 2)
        self.assertIn("INPUT_JSON_INVALID", err.getvalue())
        self.assertNotIn("invalid", out.getvalue())


if __name__ == "__main__":
    unittest.main()
