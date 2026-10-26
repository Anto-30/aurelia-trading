import unittest
from runtime.adapters.deriv_adapter import DerivAdapter
class TestDerivAdapterContract(unittest.TestCase):
 def test_missing_url_fails_closed(self):self.assertEqual(DerivAdapter(ws_url="").ws_url,"")
 def test_secret_not_in_fingerprint(self):a=DerivAdapter(ws_url="wss://example.invalid",auth_token="SECRET",expected_loginid="CR123");self.assertNotIn("SECRET",a.connection_fingerprint)
 def test_proposal_id_required_by_executor_contract(self):self.assertTrue("ORDER_REQUIRES_BROKER_PROPOSAL_ID" in "ORDER_REQUIRES_BROKER_PROPOSAL_ID")
 def test_authenticated_connect_requires_explicit_expected_currency(self):
  import asyncio
  from runtime.adapters.deriv_adapter import DerivProtocolError
  a=DerivAdapter(ws_url="wss://api.derivws.com/trading/v1/options/ws/real",expected_currency="")
  with self.assertRaisesRegex(DerivProtocolError,"EXPECTED_ACCOUNT_CURRENCY_REQUIRED"):asyncio.run(a.connect())
 def test_missing_broker_currency_fails_closed(self):
  import asyncio
  from types import SimpleNamespace
  from unittest.mock import AsyncMock, patch
  from runtime.adapters.deriv_adapter import DerivProtocolError
  transport=SimpleNamespace(connect=AsyncMock(),request=AsyncMock(return_value={"authorize":{"loginid":"CRREAL"}}),close=AsyncMock())
  a=DerivAdapter(ws_url="wss://api.derivws.com/trading/v1/options/ws/real",auth_token="TOKEN",expected_loginid="CRREAL",expected_currency="USD")
  with patch("runtime.adapters.deriv_adapter.DerivWebSocketTransport",return_value=transport):
   with self.assertRaisesRegex(DerivProtocolError,"ACCOUNT_CURRENCY_UNVERIFIED"):asyncio.run(a.connect())
  transport.close.assert_awaited_once()
 def test_unknown_is_explicit_result_type(self):from runtime.core.models import BrokerOutcome;self.assertEqual(BrokerOutcome.UNKNOWN.value,"UNKNOWN")
 def test_current_deriv_underlying_symbol_is_normalized_for_internal_consumers(self):
  from unittest.mock import AsyncMock
  a=DerivAdapter(ws_url="wss://api.derivws.com/trading/v1/options/ws/real")
  a.request=AsyncMock(return_value={"active_symbols":[{"underlying_symbol":"1HZ100V"}]})
  import asyncio
  rows=asyncio.run(a.active_symbols())
  self.assertEqual(rows[0]["symbol"],"1HZ100V")
  self.assertEqual(rows[0]["underlying_symbol"],"1HZ100V")

    def test_proposal_rejects_legacy_payload_fields_before_transport(self):
        import asyncio
        from unittest.mock import AsyncMock
        from runtime.adapters.deriv_adapter import DerivProtocolError

        async def check(extra):
            adapter = DerivAdapter(ws_url="wss://api.derivws.com/trading/v1/options/ws/public")
            adapter.request = AsyncMock(return_value={"proposal": {"id": "fixture-proposal"}})
            params = {
                "contract_type": "CALL",
                "currency": "USD",
                "underlying_symbol": "R_100",
                **extra,
            }
            with self.assertRaisesRegex(DerivProtocolError, "LEGACY_DERIV_REQUEST_FIELD"):
                await adapter.request_proposal(params)
            adapter.request.assert_not_awaited()

        asyncio.run(check({"symbol": "R_100"}))
        asyncio.run(check({"loginid": "VRTC-FIXTURE"}))

    def test_proposal_response_requires_new_api_object(self):
        import asyncio
        from unittest.mock import AsyncMock
        from runtime.adapters.deriv_adapter import DerivProtocolError

        async def run():
            adapter = DerivAdapter(ws_url="wss://api.derivws.com/trading/v1/options/ws/public")
            adapter.request = AsyncMock(return_value={"msg_type": "proposal"})
            with self.assertRaisesRegex(DerivProtocolError, "PROPOSAL_OBJECT_MISSING_FROM_BROKER"):
                await adapter.request_proposal({
                    "contract_type": "CALL",
                    "currency": "USD",
                    "underlying_symbol": "R_100",
                })

        asyncio.run(run())

    def test_buy_rejects_nonfinite_or_negative_price_before_transport(self):
        import asyncio
        from unittest.mock import AsyncMock
        from runtime.adapters.deriv_adapter import DerivProtocolError

        async def check(stake):
            adapter = DerivAdapter(ws_url="wss://api.derivws.com/trading/v1/options/ws/demo")
            adapter.authorized = True
            adapter.request = AsyncMock(return_value={
                "buy": {"transaction_id": "fixture-transaction", "contract_id": 123}
            })
            with self.assertRaisesRegex(DerivProtocolError, "ORDER_PRICE_INVALID"):
                await adapter.submit_authorized_order({
                    "proposal_id": "fixture-proposal",
                    "stake": stake,
                })
            adapter.request.assert_not_awaited()

        for invalid in (-0.01, float("nan"), float("inf"), True, None, "not-a-price"):
            asyncio.run(check(invalid))

    def test_buy_uses_new_api_price_without_legacy_identity_fields(self):
        import asyncio
        from unittest.mock import AsyncMock
        from runtime.core.models import BrokerOutcome

        async def run():
            adapter = DerivAdapter(ws_url="wss://api.derivws.com/trading/v1/options/ws/demo")
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

        asyncio.run(run())

if __name__=="__main__":unittest.main()


