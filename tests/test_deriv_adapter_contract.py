from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from runtime.adapters.deriv_adapter import DerivAdapter, DerivProtocolError
from runtime.core.models import BrokerOutcome


class TestDerivAdapterContract(unittest.IsolatedAsyncioTestCase):
    def test_missing_url_fails_closed(self):
        self.assertEqual(DerivAdapter(ws_url="").ws_url, "")

    def test_secret_not_in_fingerprint(self):
        adapter = DerivAdapter(
            ws_url="wss://example.invalid",
            auth_token="SECRET",
            expected_loginid="CR123",
        )
        self.assertNotIn("SECRET", adapter.connection_fingerprint)

    async def test_proposal_rejects_legacy_payload_fields_before_transport(self):
        for legacy_field, legacy_value in (
            ("symbol", "R_100"),
            ("loginid", "VRTC-FIXTURE"),
        ):
            with self.subTest(legacy_field=legacy_field):
                adapter = DerivAdapter(
                    ws_url="wss://api.derivws.com/trading/v1/options/ws/public"
                )
                adapter.request = AsyncMock(
                    return_value={"proposal": {"id": "fixture-proposal"}}
                )
                parameters = {
                    "contract_type": "CALL",
                    "currency": "USD",
                    "underlying_symbol": "R_100",
                    legacy_field: legacy_value,
                }
                with self.assertRaisesRegex(
                    DerivProtocolError, "LEGACY_DERIV_REQUEST_FIELD"
                ):
                    await adapter.request_proposal(parameters)
                adapter.request.assert_not_awaited()

    async def test_proposal_response_requires_new_api_object(self):
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/public"
        )
        adapter.request = AsyncMock(return_value={"msg_type": "proposal"})
        with self.assertRaisesRegex(
            DerivProtocolError, "PROPOSAL_OBJECT_MISSING_FROM_BROKER"
        ):
            await adapter.request_proposal({
                "contract_type": "CALL",
                "currency": "USD",
                "underlying_symbol": "R_100",
            })

    async def test_buy_rejects_nonfinite_or_negative_price_before_transport(self):
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/demo"
        )
        adapter.authorized = True
        adapter.request = AsyncMock(return_value={
            "buy": {"transaction_id": "fixture-transaction", "contract_id": 123}
        })
        for invalid in (-0.01, float("nan"), float("inf"), True, None, "not-a-price", 10**1000):
            with self.subTest(invalid=repr(invalid)):
                adapter.request.reset_mock()
                with self.assertRaisesRegex(DerivProtocolError, "ORDER_PRICE_INVALID"):
                    await adapter.submit_authorized_order({
                        "proposal_id": "fixture-proposal",
                        "stake": invalid,
                    })
                adapter.request.assert_not_awaited()

    async def test_buy_accepts_zero_price_at_api_boundary(self):
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/demo"
        )
        adapter.authorized = True
        adapter.request = AsyncMock(return_value={
            "buy": {"transaction_id": "fixture-transaction", "contract_id": 123}
        })
        await adapter.submit_authorized_order({
            "proposal_id": "fixture-proposal",
            "stake": 0,
        })
        adapter.request.assert_awaited_once_with({
            "buy": "fixture-proposal",
            "price": 0,
        })

    async def test_buy_uses_new_api_price_without_legacy_identity_fields(self):
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/demo"
        )
        adapter.authorized = True
        adapter.request = AsyncMock(return_value={
            "buy": {"transaction_id": "fixture-transaction", "contract_id": 123}
        })
        result = await adapter.submit_authorized_order({
            "proposal_id": "fixture-proposal",
            "stake": 1.25,
            "loginid": "MUST_NOT_BE_SENT",
            "symbol": "MUST_NOT_BE_SENT",
        })
        self.assertEqual(result.outcome, BrokerOutcome.ACCEPTED)
        adapter.request.assert_awaited_once_with({
            "buy": "fixture-proposal",
            "price": 1.25,
        })
        sent = adapter.request.await_args.args[0]
        self.assertNotIn("loginid", sent)
        self.assertNotIn("symbol", sent)

    async def test_authenticated_connect_requires_explicit_expected_currency(self):
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/real",
            expected_currency="",
        )
        with self.assertRaisesRegex(
            DerivProtocolError, "EXPECTED_ACCOUNT_CURRENCY_REQUIRED"
        ):
            await adapter.connect()

    async def test_missing_broker_currency_fails_closed(self):
        transport = type("FakeTransport", (), {
            "connect": AsyncMock(),
            "request": AsyncMock(return_value={
                "authorize": {"loginid": "CRREAL"}
            }),
            "close": AsyncMock(),
        })()
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/real",
            auth_token="FIXTURE_ONLY_TOKEN",
            expected_loginid="CRREAL",
            expected_currency="USD",
        )
        with patch(
            "runtime.adapters.deriv_adapter.DerivWebSocketTransport",
            return_value=transport,
        ):
            with self.assertRaisesRegex(
                DerivProtocolError, "ACCOUNT_CURRENCY_UNVERIFIED"
            ):
                await adapter.connect()
        transport.close.assert_awaited_once()

    def test_unknown_is_explicit_result_type(self):
        self.assertEqual(BrokerOutcome.UNKNOWN.value, "UNKNOWN")

    async def test_current_underlying_symbol_is_normalized_for_internal_consumers(self):
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/real"
        )
        adapter.request = AsyncMock(return_value={
            "active_symbols": [{"underlying_symbol": "1HZ100V"}]
        })
        rows = await adapter.active_symbols()
        self.assertEqual(rows[0]["symbol"], "1HZ100V")
        self.assertEqual(rows[0]["underlying_symbol"], "1HZ100V")


if __name__ == "__main__":
    unittest.main()
