from __future__ import annotations

import io
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.deploy import provision_deriv_readonly_secrets as provisioner


def payload() -> dict[str, str]:
    return {
        "DERIV_AUTH_TOKEN": "TRADE_SCOPED_TOKEN_SENTINEL",
        "DERIV_APP_ID": "12345",
        "DERIV_EXPECTED_LOGINID": "CR123456",
        "DERIV_EXPECTED_CURRENCY": "USD",
        "DERIV_ENVIRONMENT": "real",
        "DERIV_AUTH_MODE": "pat",
    }


class ReadOnlyDerivProvisionerTests(unittest.TestCase):
    def test_trade_scoped_token_is_rejected_as_unsupported_read_only_credential(self):
        with self.assertRaisesRegex(
            provisioner.ReadOnlyProvisioningError,
            "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
        ):
            provisioner.build_env_text(payload())

    def test_provisioner_never_creates_or_overwrites_a_credential_file(self):
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "readonly.env"
            destination.write_text("EXISTING_SENTINEL=preserve\n", encoding="utf-8")
            before = destination.read_bytes()
            with self.assertRaisesRegex(
                provisioner.ReadOnlyProvisioningError,
                "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            ):
                provisioner.provision(payload(), destination)
            self.assertEqual(destination.read_bytes(), before)
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o644)

    def test_missing_or_partial_configuration_is_still_blocked(self):
        for candidate in ({}, {"DERIV_AUTH_TOKEN": "TOKEN"}, payload()):
            with self.subTest(keys=tuple(candidate)):
                with self.assertRaisesRegex(
                    provisioner.ReadOnlyProvisioningError,
                    "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
                ):
                    provisioner.build_env_text(candidate)

    def test_command_does_not_read_stdin_or_persist_secret_values(self):
        class UnreadableStdin:
            def read(self, *args, **kwargs):
                raise AssertionError("blocked provisioner must not read credentials")

        output = io.StringIO()
        errors = io.StringIO()
        with patch("sys.stdin", UnreadableStdin()), redirect_stdout(output), redirect_stderr(errors):
            result = provisioner.main()
        self.assertEqual(result, 2)
        combined = output.getvalue() + errors.getvalue()
        self.assertIn("DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", combined)
        self.assertNotIn("TRADE_SCOPED_TOKEN_SENTINEL", combined)
        self.assertIn("SECRET_VALUES_READ=false", combined)
        self.assertIn("SECRET_VALUES_WRITTEN=false", combined)


if __name__ == "__main__":
    unittest.main()
