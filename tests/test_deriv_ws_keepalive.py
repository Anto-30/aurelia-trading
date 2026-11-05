from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport


class FakeWebSocket:
    def __init__(self) -> None:
        self.incoming: asyncio.Queue[str] = asyncio.Queue()
        self.sent: list[dict] = []
        self.closed = False

    async def recv(self) -> str:
        return await self.incoming.get()

    async def send(self, raw: str) -> None:
        payload = json.loads(raw)
        self.sent.append(payload)
        if payload.get("ping") == 1:
            await self.incoming.put(json.dumps({
                "msg_type": "ping",
                "req_id": payload["req_id"],
            }))

    async def close(self) -> None:
        self.closed = True

    async def deliver(self, message: dict) -> None:
        await self.incoming.put(json.dumps(message))


class FakeConnectionFailure(Exception):
    code = 1006


class DerivWebSocketKeepaliveTests(unittest.IsolatedAsyncioTestCase):
    async def test_periodic_application_ping_is_sent_and_correlated(self) -> None:
        websocket = FakeWebSocket()

        async def fake_connect(*args, **kwargs):
            return websocket

        with patch("runtime.adapters.deriv_ws.connect", new=AsyncMock(side_effect=fake_connect)):
            transport = DerivWebSocketTransport(
                "wss://api.derivws.com/trading/v1/options/ws/public",
                application_ping_interval=0.01,
            )
            await transport.connect()
            try:
                async def enough_pings() -> None:
                    while sum(1 for item in websocket.sent if item.get("ping") == 1) < 2:
                        await asyncio.sleep(0.002)

                await asyncio.wait_for(enough_pings(), timeout=0.25)
                pings = [item for item in websocket.sent if item.get("ping") == 1]
                self.assertGreaterEqual(len(pings), 2)
                self.assertTrue(all(item["req_id"] > 0 for item in pings))
                self.assertTrue(transport._keepalive_task is not None)
                self.assertFalse(transport._keepalive_task.done())
            finally:
                await transport.close()

    async def test_ping_responses_do_not_consume_subscription_ticks(self) -> None:
        websocket = FakeWebSocket()

        async def fake_connect(*args, **kwargs):
            return websocket

        with patch("runtime.adapters.deriv_ws.connect", new=AsyncMock(side_effect=fake_connect)):
            transport = DerivWebSocketTransport(
                "wss://api.derivws.com/trading/v1/options/ws/public",
                application_ping_interval=0.01,
            )
            await transport.connect()
            stream = transport.subscribe("ticks:R_100", {"ticks": "R_100"})
            iterator = stream.__aiter__()
            next_tick = asyncio.create_task(iterator.__anext__())
            try:
                async def subscribed_and_pinged() -> None:
                    while (
                        not any(item.get("ticks") == "R_100" for item in websocket.sent)
                        or not any(item.get("ping") == 1 for item in websocket.sent)
                    ):
                        await asyncio.sleep(0.002)

                await asyncio.wait_for(subscribed_and_pinged(), timeout=0.25)
                subscription_request = next(
                    item for item in websocket.sent if item.get("ticks") == "R_100"
                )
                await websocket.deliver({
                    "msg_type": "tick",
                    "req_id": subscription_request["req_id"],
                    "tick": {"quote": 123.45, "epoch": 1},
                })
                received = await asyncio.wait_for(next_tick, timeout=0.25)
                self.assertEqual(received["msg_type"], "tick")
                self.assertEqual(received["tick"]["quote"], 123.45)
                self.assertGreaterEqual(
                    sum(1 for item in websocket.sent if item.get("ping") == 1),
                    1,
                )
            finally:
                if not next_tick.done():
                    next_tick.cancel()
                await iterator.aclose()
                await transport.close()

    async def test_close_closes_the_underlying_websocket(self) -> None:
        websocket = FakeWebSocket()

        async def fake_connect(*args, **kwargs):
            return websocket

        with patch("runtime.adapters.deriv_ws.connect", new=AsyncMock(side_effect=fake_connect)):
            transport = DerivWebSocketTransport(
                "wss://api.derivws.com/trading/v1/options/ws/public",
                application_ping_interval=0.01,
            )
            await transport.connect()
            await transport.close()

        self.assertTrue(websocket.closed)

    async def test_reader_failure_exposes_sanitized_transport_diagnostics(self) -> None:
        class BrokenWebSocket(FakeWebSocket):
            async def recv(self) -> str:
                raise FakeConnectionFailure("do not persist arbitrary exception text")

        websocket = BrokenWebSocket()

        async def fake_connect(*args, **kwargs):
            return websocket

        with patch("runtime.adapters.deriv_ws.connect", new=AsyncMock(side_effect=fake_connect)):
            transport = DerivWebSocketTransport(
                "wss://api.derivws.com/trading/v1/options/ws/public",
                application_ping_interval=0.01,
            )
            await transport.connect()
            stream = transport.subscribe("ticks:R_100", {"ticks": "R_100"})
            try:
                with self.assertRaises(DerivTransportError) as raised:
                    await asyncio.wait_for(stream.__aiter__().__anext__(), timeout=0.25)
                self.assertEqual(raised.exception.failure_type, "FakeConnectionFailure")
                self.assertEqual(raised.exception.close_code, 1006)
                self.assertNotIn(
                    "do not persist arbitrary exception text",
                    str(raised.exception),
                )
            finally:
                await transport.close()


if __name__ == "__main__":
    unittest.main()
