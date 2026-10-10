from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from runtime.adapters.deriv_adapter import DerivAdapter


class DerivStatementQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_statement_passes_utc_range_and_offset(self):
        adapter = DerivAdapter(ws_url="wss://api.derivws.com/trading/v1/options/ws/real",
            expected_currency="USD")
        adapter.request = AsyncMock(return_value={"statement":{"transactions":[{"id":"T1"}]}})
        result = await adapter.statement(limit=999, date_from=100, date_to=200, offset=5)
        self.assertEqual(result, [{"id":"T1"}])
        adapter.request.assert_awaited_once_with({
            "statement":1,"limit":999,"offset":5,"date_from":100,"date_to":200
        })

    async def test_statement_rejects_invalid_window_or_limits(self):
        adapter = DerivAdapter(expected_currency="USD")
        with self.assertRaisesRegex(ValueError,"DERIV_STATEMENT_LIMIT_INVALID"):
            await adapter.statement(limit=1000)
        with self.assertRaisesRegex(ValueError,"DERIV_STATEMENT_DATE_WINDOW_INVALID"):
            await adapter.statement(date_from=200,date_to=100)


if __name__ == "__main__":
    unittest.main()
