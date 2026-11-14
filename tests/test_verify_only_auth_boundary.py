from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from runtime.core.secrets import SecretsError, validate_secrets_at_startup


class VerifyOnlyAuthenticationBoundaryTests(unittest.TestCase):
    def test_verify_only_rejects_authenticated_deriv_probe_before_secret_reads(self) -> None:
        environment = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "DERIV_AUTH_TOKEN": "SYNTHETIC_TOKEN_SENTINEL",
            "DERIV_PAT": "SYNTHETIC_PAT_SENTINEL",
            "DERIV_APP_ID": "SYNTHETIC_APP_ID",
            "DERIV_EXPECTED_LOGINID": "SYNTHETIC_ACCOUNT_ID",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, environment, clear=True):
            with patch("runtime.core.secrets.os.getenv", wraps=os.getenv) as getenv:
                with self.assertRaisesRegex(
                    SecretsError, "VERIFY_ONLY_AUTHENTICATION_FORBIDDEN"
                ):
                    validate_secrets_at_startup()

                requested_names = [call.args[0] for call in getenv.call_args_list]

        self.assertNotIn("DERIV_AUTH_TOKEN", requested_names)
        self.assertNotIn("DERIV_PAT", requested_names)
        self.assertNotIn("DERIV_APP_ID", requested_names)
        self.assertNotIn("DERIV_EXPECTED_LOGINID", requested_names)
        self.assertNotIn("DERIV_EXPECTED_CURRENCY", requested_names)
        self.assertNotIn("DERIV_ENVIRONMENT", requested_names)

    def test_credential_free_verify_only_worker_still_starts(self) -> None:
        environment = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "false",
        }
        with patch.dict(os.environ, environment, clear=True):
            validate_secrets_at_startup()


if __name__ == "__main__":
    unittest.main()
