from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.deploy import provision_deriv_readonly_secrets as provisioner


def payload(**overrides: str) -> dict[str, str]:
    base = {
        "DERIV_AUTH_TOKEN": "",
        "DERIV_PAT": "",
        "DERIV_OAUTH_ACCESS_TOKEN": "",
        "DERIV_OAUTH_REFRESH_TOKEN": "",
        "DERIV_EXPECTED_LOGINID": "",
        "DERIV_APP_ID": "",
        "DERIV_EXPECTED_CURRENCY": "",
        "DERIV_ENVIRONMENT": "",
        "DERIV_AUTH_MODE": "none",
    }
    base.update(overrides)
    return base


class ReadOnlyDerivProvisionerTests(unittest.TestCase):
    def test_empty_payload_is_a_noop_and_creates_no_credential_file(self):
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "private" / "readonly.env"
            with patch.object(provisioner, "READONLY_FILE", destination):
                self.assertFalse(provisioner.provision(payload(), destination))
            self.assertFalse(destination.exists())

    def test_pat_is_rejected_and_never_written(self):
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "private" / "readonly.env"
            marker = "PAT_SECRET_SENTINEL"
            with patch.object(provisioner, "READONLY_FILE", destination):
                with self.assertRaisesRegex(
                    provisioner.ReadOnlyProvisioningError,
                    "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
                ):
                    provisioner.provision(payload(DERIV_PAT=marker), destination)
            self.assertFalse(destination.exists())

    def test_generic_token_is_rejected_and_never_written(self):
        marker = "GENERIC_TOKEN_SENTINEL"
        with self.assertRaisesRegex(
            provisioner.ReadOnlyProvisioningError,
            "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
        ):
            provisioner.build_env_text(payload(DERIV_AUTH_TOKEN=marker))

    def test_oauth_token_is_rejected_until_scope_is_proven(self):
        marker = "OAUTH_TOKEN_SENTINEL"
        with self.assertRaisesRegex(
            provisioner.ReadOnlyProvisioningError,
            "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
        ):
            provisioner.build_env_text(payload(DERIV_OAUTH_ACCESS_TOKEN=marker))

    def test_main_never_prints_credential_values(self):
        marker = "NEVER_PRINT_THIS_TOKEN"
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(payload(DERIV_PAT=marker)))), \
             redirect_stdout(out), redirect_stderr(err):
            status = provisioner.main()
        self.assertEqual(status, 2)
        self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", err.getvalue())
        self.assertNotIn(marker, out.getvalue() + err.getvalue())


if __name__ == "__main__":
    unittest.main()
