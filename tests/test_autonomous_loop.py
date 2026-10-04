import asyncio
import tempfile
import unittest
from datetime import datetime, timezone

from runtime.autonomous_loop import _extract_net_delta


class AutonomousLoopTests(unittest.TestCase):
    def test_extract_profit(self):
        self.assertEqual(_extract_net_delta({"profit": "2.5"}, 1.0), 2.5)

    def test_extract_payout_minus_buy(self):
        self.assertEqual(_extract_net_delta({"payout": "4.0", "buy_price": "1.5"}, 1.0), 2.5)

    def test_unresolved_settlement_is_none(self):
        self.assertIsNone(_extract_net_delta({"contract_id": "1"}, 1.0))


if __name__ == "__main__":
    unittest.main()
