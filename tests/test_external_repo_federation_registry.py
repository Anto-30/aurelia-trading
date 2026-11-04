from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts.validate_agent_tool_skill_assignments import (
    validate_intake_source_against_registry,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "external_repo_federation.json"
ALLOWED_MODES = {"SANDBOX_ONLY", "TOOLCHAIN_ONLY", "RESEARCH_ONLY", "REFERENCE_ONLY"}


class ExternalRepositoryFederationRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.repositories = cls.registry["repositories"]

    def test_registry_count_and_repository_names_are_consistent(self):
        names = [entry["repo"].casefold() for entry in self.repositories]
        self.assertEqual(self.registry["repository_count"], len(self.repositories))
        self.assertEqual(len(names), len(set(names)))

    def test_every_entry_has_an_allowlisted_mode_and_source_url(self):
        for entry in self.repositories:
            with self.subTest(repo=entry.get("repo")):
                self.assertIn(entry.get("mode"), ALLOWED_MODES)
                self.assertTrue(entry.get("source_url", "").startswith("https://github.com/"))

    def test_every_resolved_pin_is_a_full_git_commit_sha(self):
        for entry in self.repositories:
            with self.subTest(repo=entry.get("repo")):
                pin = entry.get("head_commit")
                if pin is None:
                    self.assertEqual(entry.get("pin_validation_status"), "UNRESOLVED_REPOSITORY_REDIRECT")
                else:
                    self.assertRegex(pin, re.compile(r"^[0-9a-f]{40}$"))

    def test_external_repositories_never_receive_capital_or_live_order_authority(self):
        controls = self.registry["global_controls"]
        self.assertIs(controls["capital_authority"], False)
        self.assertIs(controls["live_order_submission"], False)
        self.assertIs(controls["broker_transaction_write"], False)
        for entry in self.repositories:
            with self.subTest(repo=entry.get("repo")):
                self.assertIs(entry.get("capital_authority", False), False)
                self.assertIs(entry.get("live_order_submission", False), False)


class HistoricalIntakeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.intake = {
            "repo": "example/project",
            "source_url": "https://github.com/example/project",
            "head_commit": "a" * 40,
            "assigned_agents": ["AURELIA"],
            "mode": "SANDBOX_ONLY",
            "capital_authority": False,
        }
        self.current = {
            "repo": "example/project",
            "source_url": "https://github.com/example/project",
            "head_commit": "b" * 40,
            "assigned_agents": ["AURELIA"],
            "mode": "SANDBOX_ONLY",
            "capital_authority": False,
        }

    def test_current_pin_may_advance_without_rewriting_historical_intake(self):
        self.assertIsNone(
            validate_intake_source_against_registry(self.intake, self.current)
        )

    def test_current_pin_must_remain_a_full_commit_sha(self):
        self.current["head_commit"] = "SYNC_REQUIRED"
        with self.assertRaises(AssertionError):
            validate_intake_source_against_registry(self.intake, self.current)

    def test_policy_drift_is_still_rejected(self):
        self.current["mode"] = "RESEARCH_ONLY"
        with self.assertRaises(AssertionError):
            validate_intake_source_against_registry(self.intake, self.current)


if __name__ == "__main__":
    unittest.main()
