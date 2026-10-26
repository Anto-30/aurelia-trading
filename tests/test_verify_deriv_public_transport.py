from __future__ import annotations

import unittest

from scripts.verify_deriv_public_transport import probe_public_transport


class FakePublicTransport:
    last_instance = None

    def __init__(self, url: str, *, timeout_seconds: float):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.connected = False
        self.closed = False
        self.sent_requests = []
        self.subscriptions = []
        FakePublicTransport.last_instance = self

    async def connect(self) -> None:
        self.connected = True

    async def request(self, payload):
        self.sent_requests.append(payload)
        return {
            "active_symbols": [
                {"underlying_symbol": "R_100"},
                {"underlying_symbol": "V_100"},
            ]
        }

    def subscribe(self, key, payload):
        self.subscriptions.append((key, payload))
        async def stream():
            yield {"msg_type": "tick", "tick": {"quote": "1234.56", "epoch": 1770000000}}
        return stream()

    async def close(self) -> None:
        self.closed = True


class PublicTransportProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_probe_requires_real_tick_not_only_active_symbols(self):
        evidence = await probe_public_transport(
            FakePublicTransport,
            tick_timeout_seconds=1.0,
        )
        transport = FakePublicTransport.last_instance

        self.assertTrue(evidence["r100_symbol_available"])
        self.assertTrue(evidence["tick_stream_verified"])
        self.assertTrue(evidence["tick_quote_finite_positive"])
        self.assertEqual(evidence["active_symbol_count"], 2)
        self.assertEqual(transport.sent_requests, [{"active_symbols": "brief"}])
        self.assertEqual(transport.subscriptions, [("ticks:R_100", {"ticks": "R_100"})])
        self.assertTrue(transport.closed)

    async def test_missing_r100_fails_closed(self):
        class NoR100Transport(FakePublicTransport):
            async def request(self, payload):
                return {"active_symbols": [{"underlying_symbol": "V_100"}]}

        with self.assertRaisesRegex(RuntimeError, "PUBLIC_R100_SYMBOL_UNAVAILABLE"):
            await probe_public_transport(NoR100Transport, tick_timeout_seconds=1.0)
        self.assertTrue(NoR100Transport.last_instance.closed)


if __name__ == "__main__":
    unittest.main()
