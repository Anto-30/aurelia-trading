from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from scripts.verify_deriv_public_transport import verify_tick_subscription


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __aiter__(self):
        return self

    async def __anext__(self):
        return self.message

    async def aclose(self):
        return None


class FakeTransport:
    def __init__(self, url, *, timeout_seconds):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.last_reader_error = None
        self.connect = AsyncMock()
        self.close = AsyncMock()
        self.stream = FakeStream({
            "msg_type": "tick",
            "tick": {"symbol": "R_100", "quote": 100.5, "epoch": 1},
        })

    def subscribe(self, key, payload):
        return self.stream


class DerivPublicTransportProbeTest(unittest.IsolatedAsyncioTestCase):
    async def test_tick_subscription_probe_verifies_symbol(self):
        result = await verify_tick_subscription(transport_factory=FakeTransport)
        self.assertTrue(result["verified"])
        self.assertEqual(result["symbol"], "R_100")
        self.assertEqual(result["observation_count"], 1)

    async def test_tick_subscription_probe_returns_sanitized_reader_failure(self):
        class FailingTransport(FakeTransport):
            def __init__(self, url, *, timeout_seconds):
                super().__init__(url, timeout_seconds=timeout_seconds)
                self.connect.side_effect = RuntimeError("offline")

        result = await verify_tick_subscription(transport_factory=FailingTransport)
        self.assertFalse(result["verified"])
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertEqual(result["error_code"], None)


if __name__ == "__main__":
    unittest.main()
