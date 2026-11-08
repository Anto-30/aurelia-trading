from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts.verify_deriv_transaction_lifecycle import run


class DerivTransactionLifecycleCurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_unsupported_currency_blocks_before_broker_bootstrap(self):
        env = {
            "DERIV_LIFECYCLE_MODE": "VERIFY_ONLY",
            "DERIV_AUTH_TOKEN": "test-token",
            "DERIV_EXPECTED_LOGINID": "CRTEST",
            "DERIV_EXPECTED_CURRENCY": "EUR",
            "DERIV_ENVIRONMENT": "real",
        }
        output = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch(
            "scripts.verify_deriv_transaction_lifecycle.get_optional_secret",
            return_value="test-token",
        ) as secret_reader, patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivSessionManager.bootstrap"
        ) as bootstrap, redirect_stdout(output):
            self.assertEqual(await run(), 2)
            bootstrap.assert_not_called()
            secret_reader.assert_not_called()
        self.assertIn("REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", output.getvalue())


if __name__ == "__main__":
    unittest.main()
