from __future__ import annotations

import json
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
