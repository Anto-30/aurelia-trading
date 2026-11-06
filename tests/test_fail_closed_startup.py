from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import runtime.main as main_module
from runtime.adapters.deriv_adapter import DerivProtocolError


class FailClosedStartupTests(unittest.TestCase):
    def test_legacy_generic_token_is_rejected_before_runtime_starts(self) -> None:
        from runtime.core.secrets import SecretsError

        env = {
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_APP_ID": "test-app-id",
            "DERIV_EXPECTED_LOGINID": "CRTEST123",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
            "DERIV_AUTH_MODE": "pat",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "AURELIA_VERIFY_DERIV_PUBLIC": "false",
            "AURELIA_RUN_ONCE": "false",
            "AURELIA_CONTINUOUS_RUNTIME": "true",
        }

        with patch.dict(os.environ, env, clear=False), \
             patch.object(main_module, "start_server") as start_server, \
             patch.object(main_module, "start_continuous_runtime", new=AsyncMock()) as start_runtime:
            with self.assertRaisesRegex(
                SecretsError,
                "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            ):
                asyncio.run(main_module.main())

        start_server.assert_not_called()
        start_runtime.assert_not_awaited()

    def test_non_production_soak_is_secret_free_only_when_fully_sealed(self) -> None:
        from runtime.core.secrets import SecretsError, validate_secrets_at_startup

        sealed = {
            "AURELIA_NON_PRODUCTION_SOAK": "true",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_VERIFY_DERIV_PUBLIC": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "false",
            "AURELIA_CONTINUOUS_RUNTIME": "false",
            "DERIV_AUTH_TOKEN": "",
            "DERIV_APP_ID": "",
        }
        with patch.dict(os.environ, sealed, clear=True):
            validate_secrets_at_startup()

        unsafe = dict(sealed)
        unsafe["LIVE_EXECUTION"] = "ENABLED"
        with patch.dict(os.environ, unsafe, clear=True):
            with self.assertRaises(SecretsError):
                validate_secrets_at_startup()


if __name__ == "__main__":
    unittest.main()
