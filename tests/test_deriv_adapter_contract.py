import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from runtime.adapters.deriv_adapter import DerivAdapter, DerivProtocolError
from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport


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

    def test_authenticated_connect_is_blocked_before_transport(self):
        transport = SimpleNamespace(connect=AsyncMock(), close=AsyncMock())
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/real",
            auth_token="DO_NOT_READ",
            expected_loginid="CRREAL",
            expected_currency="USD",
        )
        with patch("runtime.adapters.deriv_adapter.DerivWebSocketTransport", return_value=transport):
            with self.assertRaisesRegex(
                DerivProtocolError, "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"
            ):
                asyncio.run(adapter.connect())
        transport.connect.assert_not_awaited()

    def test_account_websocket_transport_is_blocked_directly(self):
        transport = DerivWebSocketTransport(
            "wss://api.derivws.com/trading/v1/options/ws/demo?otp=ONE_TIME"
        )
        with self.assertRaisesRegex(
            DerivTransportError, "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"
        ):
            asyncio.run(transport.connect())

    def test_public_symbol_normalization_remains_available(self):
        adapter = DerivAdapter(ws_url="wss://api.derivws.com/trading/v1/options/ws/public")
        adapter.request = AsyncMock(
            return_value={"active_symbols": [{"underlying_symbol": "1HZ100V"}]}
        )
        rows = asyncio.run(adapter.active_symbols())
        self.assertEqual(rows[0]["symbol"], "1HZ100V")
        self.assertEqual(rows[0]["underlying_symbol"], "1HZ100V")


if __name__ == "__main__":
    unittest.main()
