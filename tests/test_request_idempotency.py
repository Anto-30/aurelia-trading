from __future__ import annotations

import asyncio
import time
import unittest

from runtime.adapters.deriv_adapter import DerivAdapter, DerivProtocolError
from runtime.adapters.deriv_ws import DerivTransportError
from runtime.core.request_ledger import RequestLedger, RequestState


class FakeTransport:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls: list[dict] = []

    async def request(self, payload: dict) -> dict:
        self.calls.append(dict(payload))
        if self.fail:
            raise DerivTransportError("simulated transport failure")
        return {"req_id": payload["req_id"], "ok": True}


class RequestIdempotencyTests(unittest.TestCase):
    def test_every_outgoing_request_has_unique_integer_req_id(self) -> None:
        async def run() -> None:
            adapter = DerivAdapter()
            transport = FakeTransport()
            adapter.transport = transport
            await adapter.request({"balance": 1})
            await adapter.request({"active_symbols": "brief"})
            await adapter.request({"portfolio": 1})

            ids = [payload["req_id"] for payload in transport.calls]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(all(isinstance(value, int) for value in ids))

        asyncio.run(run())

    def test_transport_failure_marks_request_timeout(self) -> None:
        async def run() -> None:
            adapter = DerivAdapter()
            transport = FakeTransport(fail=True)
            adapter.transport = transport
            with self.assertRaises(DerivProtocolError):
                await adapter.request({"balance": 1})

            tracked = adapter.ledger.pending_requests[-1]
            self.assertEqual(tracked.req_id, transport.calls[0]["req_id"])
            self.assertEqual(tracked.state, RequestState.TIMEOUT)

        asyncio.run(run())

    def test_expire_stale_ages_out_old_pending_requests(self) -> None:
        ledger = RequestLedger(max_pending_age_seconds=1.0)
        tracked = ledger.create_request("balance", {"balance": 1})
        tracked.created_at = time.time() - 2.0
        expired = ledger.expire_stale()

        self.assertEqual(len(expired), 1)
        self.assertIs(expired[0], tracked)
        self.assertEqual(expired[0].state, RequestState.TIMEOUT)
        self.assertEqual(ledger.pending_count, 0)


if __name__ == "__main__":
    unittest.main()
