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
