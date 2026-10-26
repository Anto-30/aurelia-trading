from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport, Subscription
import research.r100_prospective_oos_collector as collector


class BrokenSocket:
    async def recv(self):
        raise ConnectionResetError("private-test-marker-token=not-for-logs")


class FakeStream:
    def __init__(self, outcome):
        self.outcome = outcome

    def __aiter__(self):
        return self

    async def __anext__(self):
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        raise asyncio.TimeoutError()


class FakeTransport:
    instances = []

    def __init__(self, url, *, timeout_seconds=10.0):
        self.url = url
        self.closed = False
        self.__class__.instances.append(self)

    async def connect(self):
        return None

    def subscribe(self, key, payload):
        if len(self.__class__.instances) == 1:
            return FakeStream(DerivTransportError(
                "TRANSPORT_READER_FAILED",
                code="TRANSPORT_READER_FAILED",
                cause_type="ConnectionResetError",
            ))
        return FakeStream(asyncio.TimeoutError())

    async def close(self):
        self.closed = True

    async def request(self, payload):
        raise AssertionError("no signal should be evaluated in this test")


class DerivTransportDiagnosticsTests(unittest.TestCase):

    def test_connect_starts_application_level_keepalive_task(self):
        async def run():
            class IdleSocket:
                def __init__(self):
                    self.closed = False
                    self.release = asyncio.Event()

                async def recv(self):
                    await self.release.wait()
                    return "{}"

                async def send(self, _message):
                    return None

                async def close(self):
                    self.closed = True
                    self.release.set()

            socket = IdleSocket()
            transport = DerivWebSocketTransport(
                "wss://api.derivws.com/trading/v1/options/ws/public"
            )
            with patch(
                "runtime.adapters.deriv_ws.connect",
                new=AsyncMock(return_value=socket),
            ):
                await transport.connect()
                self.assertIsNotNone(
                    getattr(transport, "_heartbeat_task", None),
                    "public transport must start an application-level Deriv ping loop",
                )
                await transport.close()

        asyncio.run(run())
    def test_reader_failure_preserves_safe_cause_type_without_raw_error_text(self):
        async def run():
            transport = DerivWebSocketTransport("wss://example.invalid/public")
            queue = asyncio.Queue()
            transport.ws = BrokenSocket()
            sub = Subscription(key="ticks:R_100", payload={}, queue=queue, request_id=7)
            transport._subscriptions[sub.key] = sub
            transport._subscription_by_request_id[7] = sub.key

            await transport._reader_loop()
            error = await queue.get()
            self.assertEqual(error["error"]["code"], "TRANSPORT_READER_FAILED")
            self.assertEqual(error["error"]["cause_type"], "ConnectionResetError")
            self.assertNotIn("private-test-marker-token", str(error))
        asyncio.run(run())

    def test_collector_reconnects_once_after_classified_reader_failure(self):
        async def run():
            FakeTransport.instances.clear()
            state = collector.initial_state()
            with (
                patch.object(collector, "DerivWebSocketTransport", FakeTransport),
                patch.object(collector, "COLLECTION_SECONDS", 3),
                patch.object(collector.asyncio, "sleep", new=AsyncMock()),
            ):
                await collector.collect_once(state)

            self.assertEqual(len(FakeTransport.instances), 2)
            self.assertTrue(FakeTransport.instances[0].closed)
            self.assertTrue(FakeTransport.instances[1].closed)
            self.assertEqual(state["last_run_reconnect_attempts"], 1)
            self.assertEqual(len(state["last_run_transport_events"]), 1)
            self.assertEqual(
                state["last_run_transport_events"][0]["cause_type"],
                "ConnectionResetError",
            )

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
