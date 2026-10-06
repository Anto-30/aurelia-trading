from __future__ import annotations

import json
import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from runtime.agent_federation import PersistentAgentFederation
from runtime.core.authority import authorization_gate
from runtime.core.models import AccountIdentity, CapitalSnapshot, Decision


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "intelligence_source_routing.json"

REQUIRED_SOURCES = {
    "GitHub",
    "CodeRabbit",
    "Next Stock Outlook",
    "The Fly Market Intelligence",
    "Sixtyfour Intelligence",
    "Code Tytor: Python",
    "Notion",
    "Outlook Email",
    "Email",
}


class IntelligenceSourceRoutingTests(unittest.TestCase):
    def test_registry_exists_and_is_valid_json(self) -> None:
        self.assertTrue(REGISTRY.is_file())
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("schema"), "aurelia.intelligence_source_routing.v1")
        self.assertIn("routing", payload)
        self.assertIsInstance(payload["routing"], list)

    def test_global_authority_invariants_remain_fail_closed(self) -> None:
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        controls = payload["invariants"]

        self.assertIs(controls["capital_authority"], False)
        self.assertIs(controls["live_order_authority"], False)
        self.assertIs(controls["production_deployment_authority"], False)
        self.assertIs(controls["secret_reading"], False)
        self.assertIs(controls["secret_logging"], False)
        self.assertEqual(controls["external_code_execution"], "DENY_BY_DEFAULT")
        self.assertIs(controls["source_pinning_required"], True)
        self.assertIs(controls["research_sources_never_override_deterministic_gates"], True)
        self.assertIs(controls["external_market_signals_are_non_authoritative"], True)

    def test_required_sources_are_explicitly_routed(self) -> None:
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        routed = {entry["source"] for entry in payload["routing"]}
        self.assertTrue(REQUIRED_SOURCES.issubset(routed))

    def test_no_source_receives_capital_authority(self) -> None:
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))

        for entry in payload["routing"]:
            self.assertNotEqual(entry.get("authority"), "capital")
            self.assertNotIn("capital", entry.get("authority", "").lower())

    def test_sources_are_unique(self) -> None:
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        sources = [entry["source"] for entry in payload["routing"]]
        self.assertEqual(len(sources), len(set(sources)))


    def test_intelligence_source_cannot_authorize_capital_action(self) -> None:
        """External intelligence sources must never directly invoke capital plane."""
        async def attempt() -> None:
            with tempfile.TemporaryDirectory() as tmp:
                federation = PersistentAgentFederation(
                    journal_path=Path(tmp) / "events.ndjson",
                    lease_path=Path(tmp) / "leases.json",
                    task_path=Path(tmp) / "tasks.json",
                    config_hash="test-config",
                    source_hash="intelligence-test",
                )
                with self.assertRaisesRegex(
                    PermissionError,
                    "EXTERNAL_AGENT_CAPITAL_AUTHORITY_FORBIDDEN",
                ):
                    await federation.publish(
                        sender="The Fly Market Intelligence",
                        recipients=("AURELIA",),
                        message_type="INTELLIGENCE_SIGNAL",
                        payload={
                            "signal": "BUY",
                            "capital_authority": True,
                        },
                        correlation_id="intelligence-boundary-test",
                    )

        asyncio.run(attempt())

    def test_intelligence_source_must_pass_through_validation(self) -> None:
        """All intelligence must flow: source -> agent -> evidence -> validation -> gate."""
        account = AccountIdentity(
            loginid="CRTEST123",
            account_type="real",
            currency="USD",
            environment="real",
        )
        capital = CapitalSnapshot(
            balance=100.0,
            currency="USD",
            available_balance=100.0,
            captured_at=datetime.now(timezone.utc),
            source="test",
            account=account,
        )
        decision = Decision(
            decision_id="decision:intelligence-bypass",
            strategy_id="research-only",
            strategy_version="0.0.0",
            strategy_hash="test-strategy-hash",
            symbol="R_100",
            direction="CALL",
            probability=0.65,
            decision_time=datetime.now(timezone.utc),
            market_snapshot_hash="test-snapshot",
            risk_requested_stake=1.0,
        )
        gate, context = authorization_gate(
            decision=decision,
            account=account,
            capital=capital,
            config_hash="test-config",
            runtime_config_hash="test-config",
            kill_switch_off=True,
            risk_approved=False,
            firewall_approved=False,
            reconciliation_healthy=False,
            final_execution_authorization=False,
            live_trading_enabled=False,
            probability_calibrated=False,
            probability_fresh=False,
            probability_drift_ok=False,
            market_data_validated=False,
            exposure_approved=False,
        )
        self.assertFalse(gate.allowed)
        self.assertIsNone(context)
        self.assertIn("EXECUTION_FIREWALL_REJECTED", gate.reason_codes)


if __name__ == "__main__":
    unittest.main()
