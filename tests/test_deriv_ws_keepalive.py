from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport


class FakeSocket:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FailingSocket(FakeSocket):
    async def recv(self):
        raise RuntimeError("synthetic-reader-failure-detail")


class DerivWebSocketKeepaliveTests(unittest.IsolatedAsyncioTestCase):
    async def test_application_keepalive_sends_json_ping_requests(self) -> None:
        transport = DerivWebSocketTransport("wss://example.invalid")
        transport.ws = FakeSocket()
        transport.keepalive_interval = 0.001
        transport.request = AsyncMock(return_value={"msg_type": "ping"})

        task = asyncio.create_task(transport._keepalive_loop())
        try:
            await asyncio.sleep(0.006)
        finally:
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self.assertGreaterEqual(transport.request.await_count, 2)
        for call in transport.request.await_args_list:
            self.assertEqual(call.args[0], {"ping": 1})

    async def test_keepalive_failure_notifies_subscribers_and_closes_socket(self) -> None:
        transport = DerivWebSocketTransport("wss://example.invalid")
        socket = FakeSocket()
        queue: asyncio.Queue[dict] = asyncio.Queue()
        transport.ws = socket
        transport.keepalive_interval = 0.001
        transport._subscriptions["ticks"] = SimpleNamespace(queue=queue)
        transport.request = AsyncMock(
            side_effect=DerivTransportError("BROKER_REQUEST_TIMEOUT")
        )

        await transport._keepalive_loop()

        message = await queue.get()
        self.assertEqual(message["error"]["code"], "BROKER_KEEPALIVE_FAILED")
        self.assertEqual(message["error"]["cause_type"], "DerivTransportError")
        self.assertTrue(socket.closed)

    async def test_reader_failure_exposes_exception_class_not_raw_message(self) -> None:
        transport = DerivWebSocketTransport("wss://example.invalid")
        queue: asyncio.Queue[dict] = asyncio.Queue()
        transport.ws = FailingSocket()
        transport._subscriptions["ticks"] = SimpleNamespace(queue=queue)

        await transport._reader_loop()

        message = await queue.get()
        self.assertEqual(message["error"]["code"], "TRANSPORT_READER_FAILED")
        self.assertEqual(message["error"]["cause_type"], "RuntimeError")
        self.assertNotIn(
            "synthetic-reader-failure-detail",
            str(message),
        )
        self.assertIsNone(transport.ws)


if __name__ == "__main__":
    unittest.main()
