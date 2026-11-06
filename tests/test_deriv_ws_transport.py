from __future__ import annotations

import asyncio
import json
import unittest

from runtime.adapters.deriv_ws import DerivWebSocketTransport, Subscription


class FakeWebSocket:
    def __init__(self, frames=None, error=None):
        self.frames = list(frames or [])
        self.error = error
        self.closed = False
        self.sent = []

    async def recv(self):
        if self.frames:
            return self.frames.pop(0)
        if self.error is not None:
            raise self.error
        raise asyncio.CancelledError()

    async def send(self, payload):
        self.sent.append(payload)

    async def close(self):
        self.closed = True


class FakeConnectionClosed(Exception):
    def __init__(self, code):
        super().__init__("simulated websocket close")
        self.code = code


class DerivWebSocketTransportTest(unittest.IsolatedAsyncioTestCase):
    async def test_subscription_updates_route_by_subscription_id_without_req_id(self):
        frames = [
            json.dumps({
                "req_id": 7,
                "msg_type": "tick",
                "tick": {"symbol": "R_100", "quote": 100.0},
                "subscription": {"id": "sub-7"},
            }),
            json.dumps({
                "msg_type": "tick",
                "tick": {"symbol": "R_100", "quote": 101.0},
                "subscription": {"id": "sub-7"},
            }),
        ]
        ws = FakeWebSocket(frames=frames)
        transport = DerivWebSocketTransport("wss://example.invalid")
        subscription = Subscription(
            key="ticks:R_100",
            payload={"ticks": "R_100"},
            queue=asyncio.Queue(),
            request_id=7,
        )
        transport.ws = ws
        transport._subscriptions[subscription.key] = subscription
        transport._subscription_by_request_id[7] = subscription.key

        with self.assertRaises(asyncio.CancelledError):
            await transport._reader_loop()

        first = subscription.queue.get_nowait()
        second = subscription.queue.get_nowait()
        self.assertEqual(first["tick"]["quote"], 100.0)
        self.assertEqual(second["tick"]["quote"], 101.0)
        self.assertEqual(transport._subscription_by_id["sub-7"], "ticks:R_100")
        self.assertTrue(ws.closed)

    async def test_subscription_close_forgets_server_subscription_id(self):
        ws = FakeWebSocket()
        transport = DerivWebSocketTransport("wss://example.invalid")
        transport.ws = ws
        stream = transport.subscribe("ticks:R_100", {"ticks": "R_100"})
        next_message = asyncio.create_task(stream.__anext__())

        for _ in range(10):
            if ws.sent:
                break
            await asyncio.sleep(0)
        self.assertEqual(json.loads(ws.sent[0]), {
            "ticks": "R_100",
            "subscribe": 1,
            "req_id": 1,
        })

        subscription = transport._subscriptions["ticks:R_100"]
        subscription.subscription_id = "server-stream-id-12345678901234567890123456789012"
        subscription.queue.put_nowait({
            "msg_type": "tick",
            "tick": {"symbol": "R_100", "quote": 100.0},
            "subscription": {"id": subscription.subscription_id},
        })
        self.assertEqual((await next_message)["tick"]["quote"], 100.0)
        await stream.aclose()

        forget = json.loads(ws.sent[-1])
        self.assertEqual(
            forget["forget"],
            "server-stream-id-12345678901234567890123456789012",
        )
        self.assertEqual(forget["req_id"], 2)

    async def test_reader_failure_preserves_exception_type_and_close_code(self):
        ws = FakeWebSocket(error=FakeConnectionClosed(1006))
        transport = DerivWebSocketTransport("wss://example.invalid")
        subscription = Subscription(
            key="ticks:R_100",
            payload={"ticks": "R_100"},
            queue=asyncio.Queue(),
            request_id=7,
        )
        transport.ws = ws
        transport._subscriptions[subscription.key] = subscription
        transport._subscription_by_request_id[7] = subscription.key

        await transport._reader_loop()

        self.assertEqual(transport.last_reader_error["code"], "TRANSPORT_READER_FAILED")
        self.assertEqual(transport.last_reader_error["exception_type"], "FakeConnectionClosed")
        self.assertEqual(transport.last_reader_error["websocket_close_code"], 1006)
        queued = subscription.queue.get_nowait()
        self.assertEqual(queued["error"]["exception_type"], "FakeConnectionClosed")
        self.assertTrue(ws.closed)

    async def test_non_object_frame_fails_with_safe_diagnostic(self):
        ws = FakeWebSocket(frames=[json.dumps(["not", "an", "object"])])
        transport = DerivWebSocketTransport("wss://example.invalid")
        subscription = Subscription(
            key="ticks:R_100",
            payload={"ticks": "R_100"},
            queue=asyncio.Queue(),
            request_id=7,
        )
        transport.ws = ws
        transport._subscriptions[subscription.key] = subscription

        await transport._reader_loop()

        self.assertEqual(transport.last_reader_error["code"], "WEBSOCKET_MESSAGE_NOT_OBJECT")
        self.assertEqual(subscription.queue.get_nowait()["error"]["code"], "WEBSOCKET_MESSAGE_NOT_OBJECT")


if __name__ == "__main__":
    unittest.main()
