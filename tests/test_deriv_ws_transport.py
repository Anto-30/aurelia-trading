from __future__ import annotations

import asyncio
import json
import unittest

from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport


class BrokenWebSocket:
    """Small fake whose recv failure includes details that must not escape."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.sent_event = asyncio.Event()
        self.close_calls = 0

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))
        self.sent_event.set()

    async def recv(self) -> str:
        await self.sent_event.wait()
        raise ConnectionResetError("PRIVATE_DETAIL_MUST_NOT_BE_PROPAGATED")

    async def close(self) -> None:
        self.close_calls += 1


class DerivWebSocketTransportDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_stale_reader_closes_its_socket_without_clearing_replacement(self):
        transport = DerivWebSocketTransport("wss://unit.test", timeout_seconds=1)
        old_socket = BrokenWebSocket()
        replacement_socket = BrokenWebSocket()
        transport.ws = old_socket  # type: ignore[assignment]
        reader = asyncio.create_task(transport._reader_loop())
        transport._reader_task = reader

        # Allow the reader to bind to the original socket before replacement.
        await asyncio.sleep(0)
        transport.ws = replacement_socket  # type: ignore[assignment]
        old_socket.sent_event.set()
        await asyncio.wait_for(reader, timeout=1)

        self.assertIs(transport.ws, replacement_socket)
        self.assertEqual(old_socket.close_calls, 1)
        await transport.close()
        self.assertEqual(replacement_socket.close_calls, 1)
        self.assertIsNone(transport.ws)

    async def test_reader_failure_exposes_safe_code_and_cause_type(self):
        transport = DerivWebSocketTransport("wss://unit.test", timeout_seconds=1)
        fake = BrokenWebSocket()
        transport.ws = fake  # type: ignore[assignment]
        transport._reader_task = asyncio.create_task(transport._reader_loop())

        stream = transport.subscribe("ticks:R_100", {"ticks": "R_100"})
        with self.assertRaises(DerivTransportError) as raised:
            await asyncio.wait_for(anext(stream), timeout=1)

        await transport._reader_task
        self.assertEqual(raised.exception.code, "TRANSPORT_READER_FAILED")
        self.assertEqual(raised.exception.failure_type, "ConnectionResetError")
        self.assertEqual(str(raised.exception), "TRANSPORT_READER_FAILED:ConnectionResetError")
        self.assertNotIn("PRIVATE_DETAIL_MUST_NOT_BE_PROPAGATED", str(raised.exception))
        self.assertEqual(fake.sent[0]["ticks"], "R_100")
        self.assertEqual(fake.sent[0]["subscribe"], 1)
        await transport.close()


if __name__ == "__main__":
    unittest.main()
