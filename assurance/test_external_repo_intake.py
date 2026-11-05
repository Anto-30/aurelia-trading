from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "external_repo_federation.json"
REPORT = ROOT / "docs" / "EXTERNAL_REPO_INTAKE_2026-11-05.md"

EXPECTED_ADMITTED = {
    "deriv-com/deriv-api": {
        "commit": "fbf51f6ed7698e6c6164fb0eda4183bb27253546",
        "mode": "REFERENCE_ONLY",
    },
    "deriv-bots/digitlens-pro": {
        "commit": "68866a42bd7bd1a3e4ce4d170c7438d34a1c6402",
        "mode": "RESEARCH_ONLY",
    },
}

REJECTED = (
    "dan-da/hd-wallet-derive",
    "digiemployeeautomation/deriv-oauth-reflector",
    "colin-kiegel/rust-derive-builder",
    "JelteF/derive_more",
)


class ExternalRepoIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.repositories = {item["repo"]: item for item in cls.payload["repositories"]}
        cls.report = REPORT.read_text(encoding="utf-8")

    def test_only_relevant_sources_are_admitted_from_this_intake(self) -> None:
        for repo, expected in EXPECTED_ADMITTED.items():
            self.assertIn(repo, self.repositories)
            item = self.repositories[repo]
            self.assertEqual(item["head_commit"], expected["commit"])
            self.assertEqual(item["mode"], expected["mode"])
        for repo in REJECTED:
            self.assertNotIn(repo, self.repositories)

    def test_admitted_sources_have_no_production_or_capital_authority(self) -> None:
        for repo in EXPECTED_ADMITTED:
            item = self.repositories[repo]
            for field in (
                "capital_authority",
                "production_deployment_authority",
                "live_order_authority",
                "secret_reading",
                "secret_logging",
                "broker_transaction_write",
            ):
                self.assertIs(item[field], False, (repo, field))
            self.assertEqual(item["physical_runtime_install"], "NOT_CLAIMED")

    def test_registry_global_controls_remain_restrictive(self) -> None:
        controls = self.payload["global_controls"]
        self.assertIs(controls["capital_authority"], False)
        self.assertIs(controls["live_order_submission"], False)
        self.assertIs(controls["live_lock_mutation"], False)
        self.assertIs(controls["secret_reading"], False)
        self.assertEqual(controls["external_code_execution"], "DENY_BY_DEFAULT")

    def test_intake_report_records_rejected_sources_and_modern_api_path(self) -> None:
        for repo in REJECTED:
            self.assertIn(repo, self.report)
        self.assertIn("REFERENCE_ONLY", self.report)
        self.assertIn("RESEARCH_ONLY", self.report)
        self.assertIn("Authorization Code + PKCE", self.report)
        self.assertIn("ws.derivws.com/websockets/v3", self.report)


if __name__ == "__main__":
    unittest.main()
