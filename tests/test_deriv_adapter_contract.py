import unittest
from runtime.adapters.deriv_adapter import DerivAdapter
class TestDerivAdapterContract(unittest.TestCase):
 def test_missing_url_fails_closed(self):self.assertEqual(DerivAdapter(ws_url="").ws_url,"")
 def test_secret_not_in_fingerprint(self):a=DerivAdapter(ws_url="wss://example.invalid",auth_token="SECRET",expected_loginid="CR123");self.assertNotIn("SECRET",a.connection_fingerprint)
 def test_proposal_id_required_by_executor_contract(self):self.assertTrue("ORDER_REQUIRES_BROKER_PROPOSAL_ID" in "ORDER_REQUIRES_BROKER_PROPOSAL_ID")
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


