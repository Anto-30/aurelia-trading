from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from runtime.core.health import HealthSnapshot
from runtime.core.journal import AppendOnlyJournal
from runtime.core.models import AccountIdentity, CapitalSnapshot
from runtime.main import _readiness_publisher, _write_runtime_deriv_evidence
from runtime.ops.readiness_orchestrator import _current_evidence


def snapshot(environment: str = "real") -> CapitalSnapshot:
    account_type = "real" if environment == "real" else "demo"
    account = AccountIdentity("CRTEST123", account_type, "USD", environment)
    now = datetime.now(timezone.utc)
    return CapitalSnapshot(
        balance=10.0,
        currency="USD",
        available_balance=10.0,
        captured_at=now,
        source="deriv:balance",
        account=account,
    )


class RuntimeReadinessPublicationTests(unittest.TestCase):
    def test_real_runtime_balance_writes_short_lived_non_authorizing_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "deriv_authenticated_session.json"
            with patch.dict(
                os.environ,
                {
                    "GITHUB_SHA": "test-source-sha",
                    "AURELIA_DERIV_EVIDENCE_PATH": str(output),
                },
            ):
                _write_runtime_deriv_evidence(snapshot(), "test-config-hash")

            self.assertTrue(output.exists())
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertIsNotNone(_current_evidence(output))
            self.assertEqual(record["observed"]["account_loginid"], "CRTEST123")
            self.assertEqual(record["observed"]["environment"], "real")
            self.assertEqual(record["orders_submitted"], 0)
            self.assertIs(record["capital_authority_granted"], False)
            self.assertIs(record["order_submission_permitted"], False)
            self.assertEqual(record["provenance"]["origin"], "runtime")
            self.assertEqual(record["source_hash"], "test-source-sha")

    def test_demo_balance_cannot_satisfy_real_runtime_evidence_gate(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "deriv_authenticated_session.json"
            with patch.dict(
                os.environ,
                {
                    "GITHUB_SHA": "test-source-sha",
                    "AURELIA_DERIV_EVIDENCE_PATH": str(output),
                },
            ):
                _write_runtime_deriv_evidence(snapshot("demo"), "test-config-hash")
            self.assertIsNone(_current_evidence(output))


class ReadinessPublisherTests(unittest.IsolatedAsyncioTestCase):
    async def test_evaluation_error_writes_explicit_blocked_report(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "AURELIA_READINESS.json"
            health = HealthSnapshot(process_heartbeat=datetime.now(timezone.utc))
            journal = AppendOnlyJournal(Path(td) / "events.ndjson")
            env = {
                "AURELIA_READINESS_PATH": str(output),
                "AURELIA_READINESS_REFRESH_SECONDS": "2",
            }
            with patch.dict(os.environ, env), patch(
                "runtime.main.evaluate_readiness", side_effect=OSError("simulated")
            ):
                task = asyncio.create_task(
                    _readiness_publisher(health, journal, "test-config-hash")
                )
                try:
                    for _ in range(50):
                        if output.exists():
                            break
                        await asyncio.sleep(0.01)
                    self.assertTrue(output.exists())
                finally:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task

            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertIs(report["final_execution_authorization"], False)
            self.assertEqual(report["live_execution"], "BLOCKED")
            self.assertEqual(report["blockers"][0]["gate"], "READINESS_REFRESH")
            self.assertIn("READINESS_PUBLISHER_FAILURE", health.critical_unknowns)


if __name__ == "__main__":
    unittest.main()
