from __future__ import annotations

import io
import json
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.deploy import provision_deriv_readonly_secrets as provisioner


def payload(mode: str = "pat") -> dict[str, str]:
    return {
        "DERIV_AUTH_TOKEN": "READ_ONLY_TOKEN_SENTINEL",
        "DERIV_APP_ID": "12345" if mode == "pat" else "",
        "DERIV_EXPECTED_LOGINID": "CR123456",
        "DERIV_EXPECTED_CURRENCY": "USD",
        "DERIV_ENVIRONMENT": "real",
        "DERIV_AUTH_MODE": mode,
    }


class ReadOnlyDerivProvisionerTests(unittest.TestCase):
    def test_valid_pat_is_written_privately_without_printing_values(self):
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "private" / "readonly.env"
            with patch.object(provisioner, "READONLY_FILE", destination), \
                 patch("sys.stdin", io.StringIO(json.dumps(payload()))), \
                 redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
                status = provisioner.main()
            output = stdout.getvalue() + stderr.getvalue()
            self.assertEqual(status, 0)
            self.assertIn("AURELIA_DERIV_READONLY_PROVISIONING=COMPLETE", output)
            self.assertIn("CAPITAL_AUTHORITY_GRANTED=false", output)
            self.assertIn("ORDER_SUBMISSION_PERMITTED=false", output)
            self.assertNotIn("READ_ONLY_TOKEN_SENTINEL", output)
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            self.assertIn("DERIV_ENVIRONMENT=real\n", destination.read_text(encoding="utf-8"))

    def test_absent_optional_credentials_is_nonfatal_noop(self):
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "readonly.env"
            with patch.object(provisioner, "READONLY_FILE", destination):
                result = provisioner.provision({
                    "DERIV_AUTH_TOKEN": "",
                    "DERIV_APP_ID": "",
                    "DERIV_EXPECTED_LOGINID": "",
                    "DERIV_EXPECTED_CURRENCY": "",
                    "DERIV_ENVIRONMENT": "real",
                    "DERIV_AUTH_MODE": "pat",
                }, destination)
            self.assertFalse(result)
            self.assertFalse(destination.exists())

    def test_partial_configuration_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "readonly.env"
            provisioner.provision(payload(), destination)
            previous = destination.read_bytes()
            bad = payload()
            bad["DERIV_EXPECTED_LOGINID"] = ""
            with self.assertRaisesRegex(
                provisioner.ReadOnlyProvisioningError, "PARTIAL_READ_ONLY_CONFIG_MISSING"
            ):
                provisioner.provision(bad, destination)
            self.assertEqual(destination.read_bytes(), previous)

    def test_oauth_does_not_require_app_id(self):
        text = provisioner.build_env_text(payload("oauth"))
        self.assertIsNotNone(text)
        self.assertIn("DERIV_AUTH_MODE=oauth\n", text)
        self.assertNotIn("DERIV_APP_ID=", text)

    def test_demo_and_newline_are_bounded_to_readonly_mode(self):
        bad = payload()
        bad["DERIV_ENVIRONMENT"] = "virtual"
        with self.assertRaisesRegex(provisioner.ReadOnlyProvisioningError, "DERIV_ENVIRONMENT_INVALID"):
            provisioner.build_env_text(bad)
        bad = payload()
        bad["DERIV_AUTH_TOKEN"] = "token\nINJECTED=true"
        with self.assertRaisesRegex(provisioner.ReadOnlyProvisioningError, "MULTILINE_VALUE_REJECTED_DERIV_AUTH_TOKEN"):
            provisioner.build_env_text(bad)


if __name__ == "__main__":
    unittest.main()
