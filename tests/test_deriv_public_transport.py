from __future__ import annotations

import asyncio
import unittest

from scripts.verify_deriv_public_transport import probe


class FakeTransport:
    def __init__(self, url: str, *, timeout_seconds: float = 10.0):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.closed = False
        self.active_symbols = [{"underlying_symbol": "1HZ100V"}]
        self.ticks = [
            {"tick": {"symbol": "1HZ100V", "quote": 1000.1, "epoch": 100}},
            {"tick": {"symbol": "1HZ100V", "quote": 1000.2, "epoch": 101}},
        ]

    async def connect(self) -> None:
        return None

    async def request(self, payload: dict) -> dict:
        if "active_symbols" in payload:
            return {"active_symbols": self.active_symbols}
        raise AssertionError("unexpected request")

    async def subscribe(self, key: str, payload: dict):
        for tick in self.ticks:
            yield tick

    async def close(self) -> None:
        self.closed = True


class PublicTransportProbeTests(unittest.TestCase):
    def test_requires_two_ordered_public_ticks(self) -> None:
        evidence = asyncio.run(probe(transport_factory=FakeTransport))
        self.assertEqual(evidence["status"], "PUBLIC_TICK_STREAM_VERIFIED")
        self.assertEqual(len(evidence["ticks"]), 2)
        self.assertFalse(evidence["authentication_used"])
        self.assertFalse(evidence["capital_authority_granted"])
        self.assertFalse(evidence["order_submission_permitted"])

    def test_rejects_non_increasing_tick_epochs(self) -> None:
        class DuplicateEpochTransport(FakeTransport):
            def __init__(self, url: str, *, timeout_seconds: float = 10.0):
                super().__init__(url, timeout_seconds=timeout_seconds)
                self.ticks[1]["tick"]["epoch"] = 100

        evidence = asyncio.run(probe(transport_factory=DuplicateEpochTransport))
        self.assertEqual(evidence["status"], "BLOCKED")
        self.assertEqual(evidence["blocker"], "PUBLIC_TICK_EPOCH_NOT_INCREASING")

    def test_rejects_inactive_symbol(self) -> None:
        class InactiveTransport(FakeTransport):
            def __init__(self, url: str, *, timeout_seconds: float = 10.0):
                super().__init__(url, timeout_seconds=timeout_seconds)
                self.active_symbols = []

        evidence = asyncio.run(probe(transport_factory=InactiveTransport))
        self.assertEqual(evidence["status"], "BLOCKED")
        self.assertEqual(evidence["blocker"], "PUBLIC_PROBE_SYMBOL_NOT_ACTIVE")


if __name__ == "__main__":
    unittest.main()
