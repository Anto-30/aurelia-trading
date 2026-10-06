from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from runtime.adapters.deriv_adapter import DerivAdapter, DerivProtocolError
from runtime.adapters.deriv_ws import DerivTransportError


class FakeTransport:
    def __init__(self):
        self.calls: list[dict] = []
        self.fail = True

    async def request(self, payload: dict) -> dict:
        self.calls.append(dict(payload))
        if self.fail:
            raise DerivTransportError("timeout")
        return {"req_id": payload["req_id"], "ok": True}


class CircuitBreakerEnforcementTests(unittest.TestCase):
    def test_sixth_transport_request_is_blocked_and_half_open_recovers(self) -> None:
        async def run(clock: list[float]) -> None:
            adapter = DerivAdapter()
            transport = FakeTransport()
            adapter.transport = transport

            with patch("runtime.core.circuit.time.monotonic", side_effect=lambda: clock[0]):
                for _ in range(5):
                    with self.assertRaises(DerivProtocolError):
                        await adapter.request({"balance": 1})

                self.assertEqual(len(transport.calls), 5)
                with self.assertRaisesRegex(
                    DerivProtocolError, "CIRCUIT_BREAKER_OPEN"
                ):
                    await adapter.request({"balance": 1})
                self.assertEqual(len(transport.calls), 5)

                clock[0] += 61.0
                transport.fail = False
                await adapter.request({"balance": 1})
                self.assertEqual(len(transport.calls), 6)
                self.assertFalse(adapter.circuit.open)

        asyncio.run(run([1000.0]))


if __name__ == "__main__":
    unittest.main()
