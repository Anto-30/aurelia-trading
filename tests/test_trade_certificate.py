import unittest
from datetime import datetime, timezone

from runtime.core.fencing import FenceToken
from runtime.core.models import AccountIdentity, AuthorizationContext, CapitalSnapshot, Decision, OrderIntent
from runtime.core.trade_certificate import TradeCertificate


class TradeCertificateTests(unittest.TestCase):
    def test_certificate_is_hashable_and_binds_authorization(self):
        account = AccountIdentity("CR123", "real", "USD", "real")
        capital = CapitalSnapshot(10.0, "USD", 10.0, datetime.now(timezone.utc), "test", account)
        decision = Decision(
            "D1", "S1", "1", "strategy-hash", "R_100", "CALL", 0.60,
            datetime.now(timezone.utc), "market-hash", 1.0, ("TEST",),
            2.0, 1.0, 0.0, 0.0, 0.0, 0.2,
        )
        authorization = AuthorizationContext(
            decision, account, capital, "config-hash", "auth-1",
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            True, True, True, True, True,
        )
        intent = OrderIntent(
            "I1", "D1", account, "R_100", "CALL", 1.0,
            datetime.now(timezone.utc), "strategy-hash", "config-hash", "LIVE", "P1",
        )
        certificate = TradeCertificate.from_authorization(
            intent=intent,
            authorization=authorization,
            fence_token=FenceToken(7, "aurelia-runtime"),
        )
        payload = certificate.as_payload()
        self.assertEqual(payload["intent_id"], "I1")
        self.assertEqual(payload["fence_generation"], 7)
        self.assertEqual(len(payload["certificate_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
