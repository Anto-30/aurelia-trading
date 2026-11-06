from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from scripts.verify_deriv_public_transport import verify_public_r100


class FakeStream:
    def __init__(self, ticks):
        self.ticks = list(ticks)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.ticks:
            raise StopAsyncIteration
        item = self.ticks.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def aclose(self):
        self.closed = True


class FakePublicClient:
    def __init__(self, ticks=None, symbols=None):
        self.ticks = ticks or [
            {"msg_type": "tick", "tick": {"symbol": "R_100", "quote": 100.1, "epoch": 10}},
            {"msg_type": "tick", "tick": {"symbol": "R_100", "quote": 100.2, "epoch": 11}},
        ]
        self.symbols = symbols or [{"underlying_symbol": "R_100"}]
        self.connect = AsyncMock()
        self.close = AsyncMock()
        self.request = AsyncMock(return_value={"active_symbols": self.symbols})
        self.historical_candles = AsyncMock(return_value=[
            {"epoch": 10, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5}
        ])
        self.stream = FakeStream(self.ticks)
        self.subscriptions = []

    def subscribe(self, key, payload):
        self.subscriptions.append((key, payload))
        return self.stream


class DerivPublicTransportProbeTests(unittest.IsolatedAsyncioTestCase):
    def test_cli_module_bootstraps_repository_root_when_run_from_scripts_directory(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "verify_deriv_public_transport.py"
        runner = (
            "import runpy, sys; "
            "from pathlib import Path; "
            "script = Path(sys.argv[1]).resolve(); "
            "root = script.parents[1]; "
            "sys.path[:] = [entry for entry in sys.path "
            "if Path(entry or '.').resolve() != root]; "
            "sys.path.insert(0, str(script.parent)); "
            "runpy.run_path(str(script), run_name='public_probe_import_test')"
        )
        result = subprocess.run(
            [sys.executable, "-c", runner, str(script)],
            cwd=script.parent,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stderr)


    async def test_probe_uses_public_client_and_requires_two_real_r100_ticks(self):
        client = FakePublicClient()
        result = await verify_public_r100(client_factory=lambda: client)
        self.assertTrue(result["verified"])
        self.assertEqual(result["authentication_mode"], "none")
        self.assertFalse(result["authorization_headers_sent"])
        self.assertFalse(result["account_credentials_loaded"])
        self.assertEqual(result["tick_count"], 2)
        self.assertEqual(result["first_tick_epoch"], 10)
        self.assertEqual(result["last_tick_epoch"], 11)
        client.connect.assert_awaited_once()
        client.request.assert_awaited_once_with({"active_symbols": "brief"})
        client.historical_candles.assert_awaited_once_with("R_100", granularity=60, count=10, end="latest")
        self.assertEqual(client.subscriptions, [("ticks:R_100", {"ticks": "R_100"})])
        self.assertTrue(client.stream.closed)
        client.close.assert_awaited_once()

    async def test_probe_rejects_tick_time_regression_without_fabricating_pass(self):
        client = FakePublicClient(ticks=[
            {"msg_type": "tick", "tick": {"symbol": "R_100", "quote": 100.1, "epoch": 10}},
            {"msg_type": "tick", "tick": {"symbol": "R_100", "quote": 100.2, "epoch": 9}},
        ])
        result = await verify_public_r100(client_factory=lambda: client)
        self.assertFalse(result["verified"])
        self.assertEqual(result["error_code"], "DERIV_PUBLIC_R100_TICK_TIME_REGRESSION")
        self.assertTrue(client.stream.closed)
        client.close.assert_awaited_once()

    async def test_probe_rejects_inactive_r100_symbol(self):
        client = FakePublicClient(symbols=[{"underlying_symbol": "R_75"}])
        result = await verify_public_r100(client_factory=lambda: client)
        self.assertFalse(result["verified"])
        self.assertEqual(result["error_code"], "DERIV_PUBLIC_R100_SYMBOL_NOT_AVAILABLE")
        client.historical_candles.assert_not_awaited()
        client.close.assert_awaited_once()

    async def test_probe_returns_failure_if_tick_stream_ends_too_early(self):
        client = FakePublicClient(ticks=[
            {"msg_type": "tick", "tick": {"symbol": "R_100", "quote": 100.1, "epoch": 10}}
        ])
        result = await verify_public_r100(client_factory=lambda: client, timeout_seconds=0.01)
        self.assertFalse(result["verified"])
        self.assertEqual(result["error_type"], "StopAsyncIteration")
        self.assertTrue(client.stream.closed)
        client.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
