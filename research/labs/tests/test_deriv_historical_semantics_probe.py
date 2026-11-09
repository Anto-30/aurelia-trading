import asyncio
import unittest

from scripts.probe_deriv_historical_semantics import probe


class FakeTransport:
    def __init__(self, url, timeout_seconds=15.0):
        self.url = url
        self.requests = []
        self.closed = False

    async def connect(self):
        return None

    async def request(self, payload):
        self.requests.append(payload)
        if payload["end"] == "latest":
            return {
                "echo_req": payload,
                "msg_type": "history",
                "history": {"times": [1794150000], "prices": [10000.0]},
            }
        if payload["style"] == "ticks":
            return {
                "echo_req": payload,
                "msg_type": "history",
                "history": {"times": [1666313940], "prices": [10000.0]},
            }
        return {
            "echo_req": payload,
            "msg_type": "candles",
            "candles": [{
                "epoch": 1666310400,
                "open": 10000.0,
                "high": 10001.0,
                "low": 9999.0,
                "close": 10000.5,
            }],
        }

    async def close(self):
        self.closed = True


class HistoricalSemanticsProbeTests(unittest.TestCase):
    def test_distinguishes_historical_boundaries_from_latest_control(self):
        fake = FakeTransport("wss://example.invalid")
        result = asyncio.run(probe(transport_factory=lambda *a, **k: fake))
        self.assertEqual(result["status"], "HISTORICAL_BOUNDARIES_VERIFIED")
        self.assertTrue(result["historical_ticks_respect_end"])
        self.assertTrue(result["historical_candles_respect_window"])
        self.assertTrue(result["adjusted_ticks_respect_end"])
        self.assertTrue(result["adjusted_candles_respect_window"])
        self.assertTrue(result["latest_control_present"])
        self.assertEqual(len(fake.requests), 5)
        self.assertTrue(fake.closed)
        self.assertFalse(result["authentication_used"])
        self.assertFalse(result["order_submission_permitted"])

    def test_adjust_start_time_result_is_not_misreported_as_exact_window(self):
        class AdjustedOnlyTransport(FakeTransport):
            async def request(self, payload):
                self.requests.append(payload)
                if payload.get("end") == "latest":
                    return {
                        "echo_req": payload,
                        "msg_type": "history",
                        "history": {"times": [1794150000], "prices": [10000.0]},
                    }
                if payload.get("adjust_start_time") == 1:
                    if payload["style"] == "ticks":
                        return {
                            "echo_req": payload,
                            "msg_type": "history",
                            "history": {"times": [1666313900], "prices": [10000.0]},
                        }
                    return {
                        "echo_req": payload,
                        "msg_type": "candles",
                        "candles": [{
                            "epoch": 1666310400,
                            "open": 10000.0,
                            "high": 10001.0,
                            "low": 9999.0,
                            "close": 10000.5,
                        }],
                    }
                if payload["style"] == "ticks":
                    return {
                        "echo_req": payload,
                        "msg_type": "history",
                        "history": {"times": [1794150000], "prices": [10000.0]},
                    }
                return {
                    "echo_req": payload,
                    "msg_type": "candles",
                    "candles": [{
                        "epoch": 1794150000,
                        "open": 10000.0,
                        "high": 10001.0,
                        "low": 9999.0,
                        "close": 10000.5,
                    }],
                }

        fake = AdjustedOnlyTransport("wss://example.invalid")
        result = asyncio.run(probe(transport_factory=lambda *a, **k: fake))
        self.assertEqual(
            result["status"],
            "ADJUST_START_TIME_RECOVERS_HISTORY_BUT_EXACT_WINDOW_UNVERIFIED",
        )
        self.assertFalse(result["historical_ticks_respect_end"])
        self.assertFalse(result["historical_candles_respect_window"])
        self.assertTrue(result["adjusted_ticks_respect_end"])
        self.assertTrue(result["adjusted_candles_respect_window"])
        self.assertTrue(fake.closed)

    def test_marks_both_historical_requests_out_of_range(self):
        class LatestForEverything(FakeTransport):
            async def request(self, payload):
                self.requests.append(payload)
                if payload["style"] == "candles":
                    return {
                        "echo_req": payload,
                        "msg_type": "candles",
                        "candles": [{
                            "epoch": 1794150000,
                            "open": 10000.0,
                            "high": 10001.0,
                            "low": 9999.0,
                            "close": 10000.5,
                        }],
                    }
                return {
                    "echo_req": payload,
                    "msg_type": "history",
                    "history": {"times": [1794150000], "prices": [10000.0]},
                }

        fake = LatestForEverything("wss://example.invalid")
        result = asyncio.run(probe(transport_factory=lambda *a, **k: fake))
        self.assertEqual(
            result["status"], "HISTORICAL_BOUNDARIES_IGNORED_OR_UNAVAILABLE"
        )
        self.assertIn(
            "BOTH_HISTORICAL_REQUESTS_RETURNED_OUTSIDE_WINDOW",
            result["blockers"],
        )
        self.assertTrue(fake.closed)


if __name__ == "__main__":
    unittest.main()
