from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from runtime.core.events import sha256
from scripts.verify_deriv_public_transport import main


class DerivPublicTransportProbeScriptTests(unittest.TestCase):
    def test_script_hash_binds_r100_tick_summary_without_quote_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "public-transport.json"
            adapter = type("FakeAdapter", (), {})()
            adapter.probe_public_market_data = AsyncMock(return_value={
                "schema": "aurelia.deriv_public_market_data_probe.v1",
                "endpoint": "wss://api.derivws.com/trading/v1/options/ws/public",
                "ping_verified": True,
                "active_symbol_count": 89,
                "tick_stream": {
                    "symbol": "R_100",
                    "ticks_received": 2,
                    "first_epoch": 1_800_000_001,
                    "last_epoch": 1_800_000_002,
                    "elapsed_ms": 50.0,
                },
                "capital_authority_granted": False,
                "order_submission_permitted": False,
            })
            with patch.dict(os.environ, {
                "DERIV_PUBLIC_TRANSPORT_EVIDENCE_OUT": str(output),
                "DERIV_PUBLIC_TICK_SYMBOL": "R_100",
                "DERIV_PUBLIC_TICK_MINIMUM": "2",
                "DERIV_PUBLIC_TICK_TIMEOUT_SECONDS": "90",
                "GITHUB_SHA": "test-source-sha",
            }):
                with patch("scripts.verify_deriv_public_transport.DerivAdapter", return_value=adapter):
                    status = asyncio.run(main())

            self.assertEqual(status, 0)
            self.assertTrue(output.exists())
            evidence = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(evidence["source_sha"], "test-source-sha")
            self.assertEqual(evidence["tick_stream"]["ticks_received"], 2)
            self.assertEqual(evidence["tick_stream"]["symbol"], "R_100")
            self.assertFalse(evidence["capital_authority_granted"])
            self.assertFalse(evidence["order_submission_permitted"])
            self.assertNotIn("quote", json.dumps(evidence))
            record_hash = evidence.pop("record_hash")
            self.assertEqual(record_hash, sha256(evidence))
            adapter.probe_public_market_data.assert_awaited_once_with(
                symbol="R_100",
                minimum_ticks=2,
                timeout_seconds=90.0,
            )


if __name__ == "__main__":
    unittest.main()
