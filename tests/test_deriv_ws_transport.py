from __future__ import annotations

import asyncio
import json
import unittest

from runtime.adapters.deriv_ws import DerivWebSocketTransport, Subscription


class BrokenSocket:
    async def recv(self):
        raise ConnectionResetError("token=must-not-be-exposed")


class DerivWebSocketReaderDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_reader_failure_reports_exception_type_without_raw_message(self):
        transport = DerivWebSocketTransport("wss://example.invalid")
        transport.ws = BrokenSocket()
        subscription = Subscription(
            key="ticks:R_100",
            payload={"ticks": "R_100"},
            queue=asyncio.Queue(),
            request_id=1,
        )
        transport._subscriptions[subscription.key] = subscription

        await transport._reader_loop()

        message = subscription.queue.get_nowait()
        self.assertEqual(message["error"]["code"], "TRANSPORT_READER_FAILED")
        self.assertEqual(message["error"]["error_type"], "ConnectionResetError")
        self.assertNotIn("must-not-be-exposed", json.dumps(message))
        self.assertNotIn("token=", json.dumps(message))
        self.assertIsNone(transport.ws)


if __name__ == "__main__":
    unittest.main()
