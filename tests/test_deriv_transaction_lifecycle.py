from __future__ import annotations

import io
import inspect
import unittest
from contextlib import redirect_stdout

import scripts.verify_deriv_transaction_lifecycle as verifier


class DerivTransactionLifecyclePolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_remains_held_without_secret_reads_or_broker_calls(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = await verifier.run()
        self.assertEqual(result, 2)
        self.assertIn(
            "REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            output.getvalue(),
        )
        self.assertIn("ORDERS_SUBMITTED=0", output.getvalue())
        self.assertIn("CAPITAL_AUTHORITY_GRANTED=false", output.getvalue())
        source = inspect.getsource(verifier)
        self.assertNotIn("get_optional_secret", source)
        self.assertNotIn("DerivSessionManager", source)
        self.assertNotIn("DerivAdapter", source)
        self.assertNotIn("DERIV_AUTH_TOKEN", source)
        self.assertNotIn("DERIV_PAT", source)


if __name__ == "__main__":
    unittest.main()
