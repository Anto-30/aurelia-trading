from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, call, patch

from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport


class FakeWebSocket:
    def __init__(self, response_factory=None):
        self.incoming = asyncio.Queue()
        self.sent = []
        self.closed = False
        self.response_factory = response_factory or self._default_response

    @staticmethod
    def _default_response(payload):
        if "balance" in payload:
            return {"balance": {"balance": 100.0, "currency": "USD", "loginid": "CRTEST"}}
        return {"echo": True}

    async def recv(self):
        return await self.incoming.get()

    async def send(self, raw):
        self.sent.append(json.loads(raw))
        payload = self.sent[-1]
        response = {
            "req_id": payload["req_id"],
            **self.response_factory(payload),
        }
        await self.incoming.put(json.dumps(response))

    async def close(self):
        self.closed = True


class DerivTransportLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_reader_correlation_and_clean_shutdown(self):
        websocket = FakeWebSocket()
        with patch(
            "runtime.adapters.deriv_ws.connect",
            new=AsyncMock(return_value=websocket),
        ) as connect:
            transport = DerivWebSocketTransport(
                "wss://api.derivws.com/trading/v1/options/ws/real",
                timeout_seconds=1.0,
                ping_interval=17.0,
            )
            await transport.connect()
            response = await transport.request({"balance": 1, "subscribe": 0})

            self.assertEqual(response["balance"]["currency"], "USD")
            self.assertEqual(response["balance"]["loginid"], "CRTEST")
            self.assertEqual(websocket.sent[0]["balance"], 1)
            self.assertIsInstance(websocket.sent[0]["req_id"], int)
            connect.assert_awaited_once_with(
                "wss://api.derivws.com/trading/v1/options/ws/real",
                ping_interval=17.0,
                ping_timeout=17.0,
                close_timeout=5,
                max_size=2_000_000,
            )

            await transport.close()
            self.assertTrue(websocket.closed)
            self.assertIsNone(transport.ws)
            self.assertIsNone(transport._reader_task)
            self.assertEqual(transport._pending, {})

    async def test_concurrent_connect_calls_create_one_socket(self):
        websocket = FakeWebSocket()
        connect_gate = asyncio.Event()
        started = asyncio.Event()

        async def connect_once(*_args, **_kwargs):
            started.set()
            await connect_gate.wait()
            return websocket

        with patch("runtime.adapters.deriv_ws.connect", new=AsyncMock(side_effect=connect_once)) as connect:
            transport = DerivWebSocketTransport("wss://example.invalid/ws/test")
            first = asyncio.create_task(transport.connect())
            await started.wait()
            second = asyncio.create_task(transport.connect())
            await asyncio.sleep(0)
            connect_gate.set()
            await asyncio.gather(first, second)
            self.assertEqual(connect.await_count, 1)
            self.assertIs(transport.ws, websocket)
            await transport.close()
            self.assertTrue(websocket.closed)

    async def test_fresh_url_reconnect_reuses_transport_object_and_closes_old_socket(self):
        first = FakeWebSocket()
        second = FakeWebSocket()
        with patch(
            "runtime.adapters.deriv_ws.connect",
            new=AsyncMock(side_effect=[first, second]),
        ) as connect:
            transport = DerivWebSocketTransport(
                "wss://api.derivws.com/trading/v1/options/ws/real",
                timeout_seconds=1.0,
            )
            instance_id = id(transport)
            await transport.connect()
            await transport.reconnect(
                "wss://api.derivws.com/trading/v1/options/ws/real?otp=TEST_ONLY"
            )

            self.assertEqual(id(transport), instance_id)
            self.assertTrue(first.closed)
            self.assertIs(transport.ws, second)
            recovered = await transport.request({"balance": 1, "subscribe": 0})
            self.assertEqual(recovered["balance"]["balance"], 100.0)
            self.assertEqual(connect.await_count, 2)
            self.assertEqual(
                connect.await_args_list,
                [
                    call(
                        "wss://api.derivws.com/trading/v1/options/ws/real",
                        ping_interval=20.0,
                        ping_timeout=20.0,
                        close_timeout=5,
                        max_size=2_000_000,
                    ),
                    call(
                        "wss://api.derivws.com/trading/v1/options/ws/real?otp=TEST_ONLY",
                        ping_interval=20.0,
                        ping_timeout=20.0,
                        close_timeout=5,
                        max_size=2_000_000,
                    ),
                ],
            )
            await transport.close()
            self.assertTrue(second.closed)

    async def test_reconnect_preserves_active_subscription_consumer(self):
        first = FakeWebSocket()
        second = FakeWebSocket()
        with patch(
            "runtime.adapters.deriv_ws.connect",
            new=AsyncMock(side_effect=[first, second]),
        ):
            transport = DerivWebSocketTransport("wss://example.invalid/ws/test")
            await transport.connect()
            iterator = transport.subscribe("ticks:R_100", {"ticks": "R_100"})
            first_event = await asyncio.wait_for(anext(iterator), timeout=0.2)
            self.assertEqual(first_event["echo"], True)

            await transport.reconnect("wss://example.invalid/ws/test?otp=FRESH_TEST")

            recovered_event = await asyncio.wait_for(anext(iterator), timeout=0.2)
            self.assertEqual(recovered_event["echo"], True)
            self.assertIn("ticks:R_100", transport._subscriptions)
            await iterator.aclose()
            await transport.close()

    async def test_close_unblocks_active_subscription_consumer(self):
        websocket = FakeWebSocket()
        websocket.send = AsyncMock()  # leave subscription waiting for its first event
        with patch(
            "runtime.adapters.deriv_ws.connect",
            new=AsyncMock(return_value=websocket),
        ):
            transport = DerivWebSocketTransport(
                "wss://example.invalid/ws/test", timeout_seconds=1.0
            )
            await transport.connect()
            iterator = transport.subscribe("ticks:R_100", {"ticks": "R_100"})
            consumer = asyncio.create_task(anext(iterator))
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            await transport.close()

            with self.assertRaises(DerivTransportError):
                await asyncio.wait_for(consumer, timeout=0.2)
            self.assertEqual(transport._subscriptions, {})
            self.assertEqual(transport._subscription_by_request_id, {})

    async def test_transport_close_cancels_pending_request_and_closes_socket(self):
        websocket = FakeWebSocket(response_factory=lambda _payload: {})
        websocket.send = AsyncMock()  # leave the request pending until close
        with patch(
            "runtime.adapters.deriv_ws.connect",
            new=AsyncMock(return_value=websocket),
        ):
            transport = DerivWebSocketTransport(
                "wss://example.invalid/ws/test", timeout_seconds=30.0
            )
            await transport.connect()
            pending = asyncio.create_task(transport.request({"balance": 1}))
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            await transport.close()
            with self.assertRaises(Exception):
                await pending
            self.assertTrue(websocket.closed)
            self.assertEqual(transport._pending, {})


if __name__ == "__main__":
    unittest.main()
