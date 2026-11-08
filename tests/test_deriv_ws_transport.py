from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from runtime.adapters.deriv_ws import DerivWebSocketTransport


class FakeWebSocket:
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.sent = []
        self.closed = False
        self.reader_error = asyncio.Event()

    async def send(self, raw):
        payload = json.loads(raw)
        self.sent.append(payload)
        await self.incoming.put(
            json.dumps({"req_id": payload["req_id"], "msg_type": "ping"})
        )

    async def recv(self):
        if self.reader_error.is_set():
            raise ConnectionResetError("SYNTHETIC_PRIVATE_TRANSPORT_DETAIL")
        raw = await self.incoming.get()
        if self.reader_error.is_set():
            raise ConnectionResetError("SYNTHETIC_PRIVATE_TRANSPORT_DETAIL")
        return raw

    async def close(self):
        self.closed = True

    def break_reader(self):
        self.reader_error.set()
        self.incoming.put_nowait(None)


class DerivWebSocketKeepaliveTests(unittest.IsolatedAsyncioTestCase):
    async def test_application_level_ping_is_sent_within_configured_interval(self):
        socket = FakeWebSocket()
        with patch(
            "runtime.adapters.deriv_ws.connect",
            new=AsyncMock(return_value=socket),
        ):
            transport = DerivWebSocketTransport(
                "wss://api.derivws.com/trading/v1/options/ws/public",
                timeout_seconds=1.0,
                application_ping_interval_seconds=0.01,
            )
            await transport.connect()
            try:
                async def ping_sent():
                    while not any(item.get("ping") == 1 for item in socket.sent):
                        await asyncio.sleep(0.001)

                await asyncio.wait_for(ping_sent(), timeout=0.5)
                self.assertTrue(
                    any(item.get("ping") == 1 for item in socket.sent)
                )
            finally:
                await transport.close()

    async def test_reader_failure_records_only_exception_class(self):
        socket = FakeWebSocket()
        with patch(
            "runtime.adapters.deriv_ws.connect",
            return_value=socket,
        ):
            transport = DerivWebSocketTransport(
                "wss://api.derivws.com/trading/v1/options/ws/public",
            )
            await transport.connect()
            reader = transport._reader_task
            socket.break_reader()
            await asyncio.wait_for(reader, timeout=0.5)
            self.assertEqual(
                getattr(transport, "_reader_error_class", None),
                "ConnectionResetError",
            )
            self.assertNotIn(
                "SYNTHETIC_PRIVATE_TRANSPORT_DETAIL",
                str(getattr(transport, "_reader_error_class", "")),
            )
            await transport.close()


if __name__ == "__main__":
    unittest.main()
