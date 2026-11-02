from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.deploy import provision_runtime_secrets as provisioner


class RuntimeSecretProvisionerTests(unittest.TestCase):
    def payload(self):
        return {
            "DERIV_AUTH_TOKEN": "GENERIC_TOKEN_SECRET_SENTINEL",
            "DERIV_PAT": "PAT_SECRET_SENTINEL",
            "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SECRET_SENTINEL",
            "DERIV_EXPECTED_LOGINID": "ACCOUNT_ID_SENTINEL",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
            "DERIV_AUTH_MODE": "oauth",
            "AURELIA_ATTESTATION_SIGNING_KEY": "SIGNING_KEY_SENTINEL",
            "AURELIA_RUNTIME_ID": "aurelia-production-worker",
            "AURELIA_OPERATOR_RESET_SIGNING_KEY": "OPERATOR_RESET_KEY_SENTINEL_32_CHARS",
        }

    def test_runtime_credential_provisioning_is_blocked_without_read_only_scope(self):
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "private" / "aurelia-live-secrets.env"
            with self.assertRaisesRegex(
                provisioner.RuntimeSecretProvisioningError,
                "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            ):
                provisioner.provision(self.payload(), destination)
            self.assertFalse(destination.exists())

    def test_build_env_text_rejects_pat_and_generic_token_payloads(self):
        for key in ("DERIV_PAT", "DERIV_AUTH_TOKEN", "DERIV_OAUTH_ACCESS_TOKEN"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    provisioner.RuntimeSecretProvisioningError,
                    "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
                ):
                    provisioner.build_env_text(self.payload())

    def test_main_does_not_echo_or_store_any_secret(self):
        payload = self.payload()
        output, error = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as td, \
             patch.object(provisioner, "LIVE_SECRET_FILE", Path(td) / "runtime.env"), \
             patch("sys.stdin", io.StringIO(json.dumps(payload))), \
             redirect_stdout(output), redirect_stderr(error):
            status = provisioner.main()
            self.assertFalse((Path(td) / "runtime.env").exists())
        self.assertEqual(status, 2)
        self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", error.getvalue())
        for secret in payload.values():
            self.assertNotIn(secret, output.getvalue() + error.getvalue())

    def test_invalid_json_is_reported_without_echoing_input(self):
        output, error = io.StringIO(), io.StringIO()
        with patch.object(provisioner, "LIVE_SECRET_FILE", Path("/not-used")), \
             patch("sys.stdin", io.StringIO("{invalid")), \
             redirect_stdout(output), redirect_stderr(error):
            status = provisioner.main()
        self.assertEqual(status, 2)
        self.assertIn("INPUT_JSON_INVALID", error.getvalue())
        self.assertNotIn("invalid", output.getvalue())


if __name__ == "__main__":
    unittest.main()
