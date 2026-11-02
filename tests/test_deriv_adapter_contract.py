import os
import unittest
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

    def test_authenticated_connect_requires_explicit_expected_currency(self):
        import asyncio

        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/real",
            expected_currency="",
        )
        with self.assertRaisesRegex(
            DerivProtocolError,
            "EXPECTED_ACCOUNT_CURRENCY_REQUIRED",
        ):
            asyncio.run(adapter.connect())

    def test_account_connect_fails_closed_even_with_distinct_oauth_token(self):
        import asyncio

        transport = AsyncMock()
        with patch.dict(
            os.environ,
            {
                "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SECRET_SENTINEL",
                "DERIV_PAT": "",
                "DERIV_AUTH_TOKEN": "",
            },
            clear=True,
        ), patch(
            "runtime.adapters.deriv_adapter.DerivWebSocketTransport",
            return_value=transport,
        ):
            adapter = DerivAdapter(
                ws_url="wss://api.derivws.com/trading/v1/options/ws/real",
                auth_token="OAUTH_SECRET_SENTINEL",
                expected_loginid="CRREAL",
                expected_currency="USD",
            )
            with self.assertRaisesRegex(
                DerivProtocolError,
                "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            ):
                asyncio.run(adapter.connect())
        transport.connect.assert_not_awaited()

    def test_legacy_generic_token_is_not_loaded_as_oauth(self):
        with patch.dict(
            os.environ,
            {
                "DERIV_AUTH_TOKEN": "PAT_FALLBACK_SENTINEL",
                "DERIV_OAUTH_ACCESS_TOKEN": "",
            },
            clear=True,
        ):
            adapter = DerivAdapter(
                ws_url="wss://api.derivws.com/trading/v1/options/ws/real",
                expected_currency="USD",
            )
        self.assertEqual(adapter.auth_token, "")

    def test_unknown_is_explicit_result_type(self):
        from runtime.core.models import BrokerOutcome

        self.assertEqual(BrokerOutcome.UNKNOWN.value, "UNKNOWN")

    def test_current_deriv_underlying_symbol_is_normalized_for_internal_consumers(self):
        import asyncio

        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/real"
        )
        adapter.request = AsyncMock(
            return_value={"active_symbols": [{"underlying_symbol": "1HZ100V"}]}
        )
        rows = asyncio.run(adapter.active_symbols())
        self.assertEqual(rows[0]["symbol"], "1HZ100V")
        self.assertEqual(rows[0]["underlying_symbol"], "1HZ100V")


if __name__ == "__main__":
    unittest.main()
