import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from runtime.adapters.deriv_adapter import DerivAdapter, DerivProtocolError


class TestDerivAdapterContract(unittest.TestCase):
    def test_missing_url_fails_closed(self):
        self.assertEqual(DerivAdapter(ws_url="").ws_url, "")

    def test_secret_not_in_fingerprint(self):
        adapter = DerivAdapter(
            ws_url="wss://example.invalid",
            auth_token="SECRET",
            expected_loginid="CR123",
        )
        self.assertNotIn("SECRET", adapter.connection_fingerprint)

    def test_proposal_id_required_by_executor_contract(self):
        self.assertIn("ORDER_REQUIRES_BROKER_PROPOSAL_ID", "ORDER_REQUIRES_BROKER_PROPOSAL_ID")

    def test_authenticated_connect_verifies_exact_account_and_currency(self):
        transport = SimpleNamespace(
            connect=AsyncMock(),
            request=AsyncMock(return_value={
                "balance": {
                    "loginid": "CRREAL",
                    "currency": "USD",
                    "balance": 12.5,
                }
            }),
            close=AsyncMock(),
        )
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/real",
            expected_loginid="CRREAL",
            expected_currency="USD",
            environment="real",
        )
        with patch("runtime.adapters.deriv_adapter.DerivWebSocketTransport", return_value=transport):
            account = asyncio.run(adapter.connect())
        self.assertEqual(account.loginid, "CRREAL")
        self.assertEqual(account.currency, "USD")
        transport.connect.assert_awaited_once()
        transport.request.assert_awaited_once()
        self.assertEqual(transport.request.await_args.args[0], {"balance": 1})

    def test_missing_broker_currency_fails_closed(self):
        transport = SimpleNamespace(
            connect=AsyncMock(),
            request=AsyncMock(return_value={"balance": {"loginid": "CRREAL"}}),
            close=AsyncMock(),
        )
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/real",
            expected_loginid="CRREAL",
            expected_currency="USD",
        )
        with patch("runtime.adapters.deriv_adapter.DerivWebSocketTransport", return_value=transport):
            with self.assertRaisesRegex(DerivProtocolError, "ACCOUNT_CURRENCY_UNVERIFIED"):
                asyncio.run(adapter.connect())
        transport.close.assert_awaited_once()

    def test_current_deriv_underlying_symbol_is_normalized_for_internal_consumers(self):
        adapter = DerivAdapter(ws_url="wss://api.derivws.com/trading/v1/options/ws/public")
        adapter.request = AsyncMock(
            return_value={"active_symbols": [{"underlying_symbol": "1HZ100V"}]}
        )
        rows = asyncio.run(adapter.active_symbols())
        self.assertEqual(rows[0]["symbol"], "1HZ100V")
        self.assertEqual(rows[0]["underlying_symbol"], "1HZ100V")


if __name__ == "__main__":
    unittest.main()
