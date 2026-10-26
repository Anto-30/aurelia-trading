from __future__ import annotations

import asyncio
import json
import unittest

from runtime.adapters.deriv_ws import DerivWebSocketTransport, Subscription


class FailingSocket:
    async def recv(self):
        raise OSError("must-not-leak-transport-detail")

    async def close(self):
        return None


class DerivReaderFailureDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_subscription_receives_safe_reader_cause_without_raw_exception(self):
        transport = DerivWebSocketTransport("wss://example.invalid")
        queue = asyncio.Queue()
        subscription = Subscription(
            key="ticks:R_100",
            payload={"ticks": "R_100", "subscribe": 1},
            queue=queue,
            request_id=1,
        )
        transport.ws = FailingSocket()
        transport._subscriptions[subscription.key] = subscription
        transport._subscription_by_request_id[1] = subscription.key

        await transport._reader_loop()
        message = await queue.get()

        self.assertEqual(message["error"]["code"], "TRANSPORT_READER_FAILED")
        self.assertEqual(message["error"]["cause_type"], "OSError")
        self.assertNotIn("must-not-leak-transport-detail", json.dumps(message))


if __name__ == "__main__":
    unittest.main()
