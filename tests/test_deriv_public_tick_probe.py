from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from runtime.adapters.deriv_adapter import DerivAdapter, DerivProtocolError


class FakePublicTransport:
    def __init__(self, *, active_symbols=None, ticks=None, stall=False) -> None:
        self.active_symbols = active_symbols or [{"underlying_symbol": "R_100"}]
        self.ticks = ticks if ticks is not None else [
            {"msg_type": "tick", "tick": {"symbol": "R_100", "quote": 100.1, "epoch": 1_800_000_001}},
            {"msg_type": "tick", "tick": {"symbol": "R_100", "quote": 100.2, "epoch": 1_800_000_002}},
        ]
        self.stall = stall
        self.connected = False
        self.closed = False
        self.requests: list[dict] = []
        self.subscriptions: list[tuple[str, dict]] = []

    async def connect(self) -> None:
        self.connected = True

    async def request(self, payload: dict) -> dict:
        self.requests.append(dict(payload))
        if payload.get("ping") == 1:
            return {"msg_type": "ping", "ping": "pong", "req_id": payload["req_id"]}
        if payload.get("active_symbols") == "brief":
            return {"msg_type": "active_symbols", "active_symbols": self.active_symbols, "req_id": payload["req_id"]}
        raise AssertionError("unexpected public request")

    async def subscribe(self, key: str, payload: dict):
        self.subscriptions.append((key, dict(payload)))
        for tick in self.ticks:
            if isinstance(tick, Exception):
                raise tick
            yield tick
        if self.stall:
            await asyncio.sleep(1.0)

    async def close(self) -> None:
        self.closed = True


class DerivPublicTickProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_probe_verifies_ping_symbols_and_two_r100_ticks(self) -> None:
        transport = FakePublicTransport(active_symbols=[
            {"underlying_symbol": "R_100"},
            {"underlying_symbol": "R_75"},
        ])
        adapter = DerivAdapter()

        with patch("runtime.adapters.deriv_adapter.DerivWebSocketTransport", return_value=transport):
            result = await adapter.probe_public_market_data(
                symbol="R_100",
                minimum_ticks=2,
                timeout_seconds=0.25,
            )

        self.assertTrue(transport.connected)
        self.assertTrue(transport.closed)
        self.assertEqual([x.get("ping") for x in transport.requests if "ping" in x], [1])
        self.assertEqual([x.get("active_symbols") for x in transport.requests if "active_symbols" in x], ["brief"])
        self.assertEqual(transport.subscriptions, [("ticks:R_100", {"ticks": "R_100"})])
        self.assertEqual(result["active_symbol_count"], 2)
        self.assertEqual(result["tick_stream"]["symbol"], "R_100")
        self.assertEqual(result["tick_stream"]["ticks_received"], 2)
        self.assertEqual(result["tick_stream"]["last_epoch"], 1_800_000_002)
        self.assertFalse(result["capital_authority_granted"])
        self.assertFalse(result["order_submission_permitted"])

    async def test_public_probe_rejects_inactive_symbol_and_closes_transport(self) -> None:
        transport = FakePublicTransport(active_symbols=[{"underlying_symbol": "R_75"}])
        adapter = DerivAdapter()

        with patch("runtime.adapters.deriv_adapter.DerivWebSocketTransport", return_value=transport):
            with self.assertRaisesRegex(DerivProtocolError, "DERIV_PUBLIC_SYMBOL_NOT_ACTIVE"):
                await adapter.probe_public_market_data(
                    symbol="R_100",
                    minimum_ticks=2,
                    timeout_seconds=0.25,
                )

        self.assertTrue(transport.closed)
        self.assertEqual(transport.subscriptions, [])

    async def test_public_probe_times_out_without_fabricating_ticks(self) -> None:
        transport = FakePublicTransport(ticks=[], stall=True)
        adapter = DerivAdapter()

        with patch("runtime.adapters.deriv_adapter.DerivWebSocketTransport", return_value=transport):
            with self.assertRaisesRegex(DerivProtocolError, "DERIV_PUBLIC_TICK_STREAM_TIMEOUT"):
                await adapter.probe_public_market_data(
                    symbol="R_100",
                    minimum_ticks=2,
                    timeout_seconds=0.01,
                )

        self.assertTrue(transport.closed)

    async def test_public_probe_rejects_tick_time_regression(self) -> None:
        transport = FakePublicTransport(ticks=[
            {"msg_type": "tick", "tick": {"symbol": "R_100", "quote": 100.1, "epoch": 10}},
            {"msg_type": "tick", "tick": {"symbol": "R_100", "quote": 100.2, "epoch": 9}},
        ])
        adapter = DerivAdapter()

        with patch("runtime.adapters.deriv_adapter.DerivWebSocketTransport", return_value=transport):
            with self.assertRaisesRegex(DerivProtocolError, "DERIV_PUBLIC_TICK_TIME_REGRESSION"):
                await adapter.probe_public_market_data(
                    symbol="R_100",
                    minimum_ticks=2,
                    timeout_seconds=0.25,
                )

        self.assertTrue(transport.closed)


if __name__ == "__main__":
    unittest.main()
