from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts.verify_deriv_transaction_lifecycle import run


class DerivTransactionLifecyclePolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_remains_held_before_credentials_or_broker_calls(self):
        output = io.StringIO()
        with patch(
            "scripts.verify_deriv_transaction_lifecycle.get_optional_secret"
        ) as secret_reader, patch(
            "scripts.verify_deriv_transaction_lifecycle.DerivSessionManager.bootstrap"
        ) as bootstrap, redirect_stdout(output):
            self.assertEqual(await run(), 2)
        secret_reader.assert_not_called()
        bootstrap.assert_not_called()
        self.assertIn("REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE", output.getvalue())


if __name__ == "__main__":
    unittest.main()
