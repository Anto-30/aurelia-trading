import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from scripts.deriv_public_ws_soak_3600 import _valid_tick, run_public_ws_soak


class FakeTransport:
    def __init__(self, url, timeout_seconds=10.0):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.closed = False
        self.reconnects = 0
        self.counter = 0
        self.last_epoch = 1_800_000_000
        self.emit_stale_after_reconnect = False

    async def connect(self):
        return None

    async def request(self, payload):
        if payload.get("active_symbols"):
            return {"active_symbols": [{"underlying_symbol": "R_100"}]}
        raise AssertionError("unexpected request")

    async def subscribe(self, key, payload):
        while not self.closed:
            await asyncio.sleep(0.002)
            if self.emit_stale_after_reconnect:
                self.emit_stale_after_reconnect = False
                yield {
                    "msg_type": "tick",
                    "tick": {
                        "symbol": "R_100",
                        "quote": 1000.0 + self.counter,
                        "epoch": self.last_epoch,
                    },
                }
                continue
            self.counter += 1
            self.last_epoch += 1
            yield {
                "msg_type": "tick",
                "tick": {
                    "symbol": "R_100",
                    "quote": 1000.0 + self.counter,
                    "epoch": self.last_epoch,
                },
            }

    async def reconnect(self):
        self.reconnects += 1
        self.emit_stale_after_reconnect = True

    async def close(self):
        self.closed = True


class DerivPublicWsSoakTests(unittest.TestCase):
    def test_controlled_reconnects_and_records_non_authoritative_evidence(self):
        async def run(root):
            fake = FakeTransport("wss://example.invalid")
            result = await run_public_ws_soak(
                symbol="R_100",
                duration_seconds=2,
                reconnect_interval_seconds=1,
                recovery_timeout_seconds=1,
                evidence_path=root / "evidence.jsonl",
                summary_path=root / "summary.json",
                transport_factory=lambda url, timeout_seconds: fake,
            )
            return result, fake

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result, fake = asyncio.run(run(root))
            self.assertEqual(result["status"], "PASS")
            self.assertGreater(result["tick_count"], 0)
            self.assertEqual(result["reconnect_count"], 1)
            self.assertEqual(result["recovery_success_count"], 1)
            evidence = [
                json.loads(line)
                for line in (root / "evidence.jsonl").read_text().splitlines()
            ]
            self.assertEqual(
                sum(
                    item["event_type"] == "STALE_PRE_RECONNECT_TICK_IGNORED"
                    for item in evidence
                ),
                1,
            )
            self.assertFalse(result["authentication_used"])
            self.assertFalse(result["capital_authority"])
            self.assertFalse(result["order_submission_permitted"])
            self.assertTrue(fake.closed)
            self.assertTrue((root / "evidence.jsonl").exists())
            self.assertTrue((root / "summary.json").exists())
            saved = json.loads((root / "summary.json").read_text())
            self.assertEqual(saved["status"], "PASS")

    def test_invalid_duration_is_rejected(self):
        async def run(root):
            return await run_public_ws_soak(
                symbol="R_100",
                duration_seconds=10,
                reconnect_interval_seconds=10,
                recovery_timeout_seconds=1,
                evidence_path=root / "evidence.jsonl",
                summary_path=root / "summary.json",
                transport_factory=FakeTransport,
            )

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                ValueError, "RECONNECT_INTERVAL_MUST_BE_SHORTER"
            ):
                asyncio.run(run(Path(directory)))


    def test_tick_parser_accepts_omitted_optional_symbol(self):
        epoch, quote = _valid_tick(
            {"msg_type": "tick", "tick": {"epoch": 1800000000, "quote": 10000.25}},
            "R_100",
        )
        self.assertEqual(epoch, 1800000000)
        self.assertEqual(quote, 10000.25)

    def test_tick_parser_rejects_mismatched_symbol_and_coercions(self):
        invalid = [
            ({"msg_type": "tick", "tick": {"symbol": "V_100", "epoch": 1800000000, "quote": 10000.0}}, "PUBLIC_TICK_SYMBOL_MISMATCH"),
            ({"msg_type": "tick", "tick": {"symbol": "R_100", "epoch": True, "quote": 10000.0}}, "PUBLIC_TICK_EPOCH_INVALID"),
            ({"msg_type": "tick", "tick": {"symbol": "R_100", "epoch": 1800000000, "quote": "10000.0"}}, "PUBLIC_TICK_QUOTE_INVALID"),
            ({"msg_type": "tick", "tick": {"symbol": "R_100", "epoch": 1800000000, "quote": True}}, "PUBLIC_TICK_QUOTE_INVALID"),
            ({"msg_type": "ohlc", "tick": {"symbol": "R_100", "epoch": 1800000000, "quote": 10000.0}}, "PUBLIC_TICK_MESSAGE_TYPE_INVALID"),
        ]
        for message, reason in invalid:
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(RuntimeError, reason):
                    _valid_tick(message, "R_100")


if __name__ == "__main__":
    unittest.main()
