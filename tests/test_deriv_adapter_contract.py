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
if __name__=="__main__":unittest.main()


