from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts.verify_deriv_transaction_lifecycle import run, verify_only_direction_matches_contract


class VerifyOnlyContractDirectionTests(unittest.TestCase):
    def test_call_contract_accepts_buy_direction(self):
        self.assertTrue(verify_only_direction_matches_contract("CALL", "BUY"))

    def test_put_contract_accepts_sell_direction(self):
        self.assertTrue(verify_only_direction_matches_contract("PUT", "SELL"))

    def test_mismatched_contract_and_direction_are_rejected(self):
        self.assertFalse(verify_only_direction_matches_contract("PUT", "BUY"))
        self.assertFalse(verify_only_direction_matches_contract("CALL", "SELL"))

    def test_unsupported_contract_is_rejected(self):
        self.assertFalse(verify_only_direction_matches_contract("DIGITOVER", "BUY"))


class DerivTransactionLifecycleCurrencyTests(unittest.IsolatedAsyncioTestCase):
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
