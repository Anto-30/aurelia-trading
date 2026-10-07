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
    def test_authentication_probe_failure_aborts_continuous_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "DERIV_AUTH_TOKEN": "test-token",
                "DERIV_APP_ID": "test-app-id",
                "DERIV_EXPECTED_LOGINID": "CRTEST123",
                "AURELIA_VERIFY_DERIV_AUTH": "true",
                "AURELIA_VERIFY_DERIV_PUBLIC": "false",
                "AURELIA_RUN_ONCE": "false",
                "AURELIA_CONTINUOUS_RUNTIME": "true",
                "AURELIA_JOURNAL_PATH": os.path.join(tmp, "events.ndjson"),
                "AURELIA_FEDERATION_JOURNAL_PATH": os.path.join(tmp, "federation.ndjson"),
                "AURELIA_FEDERATION_LEASE_PATH": os.path.join(tmp, "leases.json"),
                "AURELIA_FEDERATION_TASK_PATH": os.path.join(tmp, "tasks.json"),
            }
            fake_bootstrap = SimpleNamespace(
                websocket=SimpleNamespace(url="wss://api.derivws.com/trading/v1/options/ws/real"),
                binding=SimpleNamespace(
                    loginid="CRTEST123",
                    currency="USD",
                    environment="real",
                ),
            )
            fake_server = MagicMock()
            fake_supervisor = MagicMock()
            fake_supervisor.stop = AsyncMock()

            with patch.dict(os.environ, env, clear=False), \
                 patch.object(main_module, "start_server", return_value=fake_server), \
                 patch.object(main_module, "AgentFederationSupervisor", return_value=fake_supervisor), \
                 patch.object(main_module.DerivSessionManager, "bootstrap", return_value=fake_bootstrap), \
                 patch.object(main_module.DerivAdapter, "connect", new=AsyncMock(side_effect=DerivProtocolError("ACCOUNT_IDENTITY_MISMATCH"))), \
                 patch.object(main_module, "start_continuous_runtime", new=AsyncMock()) as start_runtime:
                with self.assertRaises(SystemExit) as ctx:
                    asyncio.run(main_module.main())

            self.assertIn(
                "AUTHENTICATED_DERIV_SESSION_VERIFICATION_FAILED",
                str(ctx.exception),
            )
            start_runtime.assert_not_awaited()
            fake_supervisor.stop.assert_awaited_once()
            fake_server.shutdown.assert_called_once()

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
