from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts.verify_deriv_transaction_lifecycle import run


class DerivTransactionLifecycleCurrencyTests(unittest.IsolatedAsyncioTestCase):

    async def test_unclassified_exception_details_are_never_printed(self):
        import io
        from contextlib import redirect_stdout

        private_text = "SYNTHETIC_PRIVATE_TOKEN_DO_NOT_LOG"
        output = io.StringIO()
        env = {
            "DERIV_LIFECYCLE_MODE": "VERIFY_ONLY",
            "DERIV_AUTH_TOKEN": "SYNTHETIC_TOKEN",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "scripts.verify_deriv_transaction_lifecycle.get_optional_secret",
            return_value="SYNTHETIC_TOKEN",
        ), patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivSessionManager.bootstrap",
            side_effect=ValueError(private_text),
        ), redirect_stdout(output):
            result = await run()

        rendered = output.getvalue()
        self.assertEqual(result, 1)
        self.assertIn("DERIV_TRANSACTION_LIFECYCLE=FAILED", rendered)
        self.assertIn("REASON=UNCLASSIFIED_VALUEERROR", rendered)
        self.assertNotIn(private_text, rendered)
        self.assertNotIn("SYNTHETIC_TOKEN", rendered)

    async def test_allowlisted_deriv_internal_reason_is_preserved(self):
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        env = {
            "DERIV_LIFECYCLE_MODE": "VERIFY_ONLY",
            "DERIV_AUTH_TOKEN": "TOKEN",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "scripts.verify_deriv_transaction_lifecycle.get_optional_secret",
            return_value="TOKEN",
        ), patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivSessionManager.bootstrap",
            side_effect=ValueError("ACCOUNT_ENVIRONMENT_MISMATCH"),
        ), redirect_stdout(output):
            result = await run()

        self.assertEqual(result, 1)
        self.assertIn("REASON=ACCOUNT_ENVIRONMENT_MISMATCH", output.getvalue())


    async def test_verify_only_otp_adapter_never_reuses_pat_authorization(self):
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from runtime.core.models import AccountIdentity, CapitalSnapshot
        from unittest.mock import AsyncMock

        account = AccountIdentity(
            loginid="CRTEST",
            account_type="real",
            currency="USD",
            environment="real",
        )
        balance = CapitalSnapshot(
            balance=10.0,
            currency="USD",
            available_balance=10.0,
            captured_at=datetime.now(timezone.utc),
            source="deriv:balance",
            account=account,
        )
        bootstrap = SimpleNamespace(
            binding=account,
            websocket=SimpleNamespace(
                url="wss://api.derivws.com/trading/v1/options/ws/real?otp=SYNTHETIC_OTP"
            ),
        )
        env = {
            "DERIV_LIFECYCLE_MODE": "VERIFY_ONLY",
            "DERIV_AUTH_TOKEN": "SYNTHETIC_PAT",
            "DERIV_APP_ID": "APP_ID",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "scripts.verify_deriv_transaction_lifecycle.get_optional_secret",
            return_value="SYNTHETIC_PAT",
        ), patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivSessionManager.bootstrap",
            return_value=bootstrap,
        ), patch(
            "scripts.verify_deriv_transaction_lifecycle.CapitalPlaneExecutor",
        ), patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivAdapter.__init__",
            return_value=None,
        ) as adapter_init, patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivAdapter.connect",
            new=AsyncMock(return_value=account),
        ), patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivAdapter.get_balance",
            new=AsyncMock(return_value=balance),
        ), patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivAdapter.active_symbols",
            new=AsyncMock(return_value=[]),
        ), patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivAdapter.close",
            new=AsyncMock(),
        ):
            result = await run()

        self.assertEqual(result, 2)
        self.assertEqual(
            adapter_init.call_args.kwargs.get("auth_token"),
            "",
            "An OTP URL is already authenticated; the PAT must not be sent again.",
        )

    async def test_unsupported_currency_blocks_before_broker_bootstrap(self):
        env = {
            "DERIV_LIFECYCLE_MODE": "VERIFY_ONLY",
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "EUR",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "scripts.verify_deriv_transaction_lifecycle.get_optional_secret",
            return_value="test-token",
        ), patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivSessionManager.bootstrap"
        ) as bootstrap:
            self.assertEqual(await run(), 2)
            bootstrap.assert_not_called()


if __name__ == "__main__":
    unittest.main()
