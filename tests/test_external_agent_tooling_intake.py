from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = (
    "research-statistics-fundamentals",
    "research-performance-metrics",
    "research-return-calculations",
    "security-operational-risk",
)
PROJECT_SKILL_ROOTS = ("skills", ".claude/skills", ".grok/skills", ".agents/skills")
CLAUDE_AGENTS = (
    "aurelia-security-auditor",
    "aurelia-secrets-hygiene-engineer",
    "aurelia-quantitative-researcher",
    "aurelia-runtime-reliability-engineer",
)
ASSIGNED_AGENTS = {"ClaudeCode", "KimiK3", "GrokBot", "JEV", "ChatGPT"}


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class ExternalAgentToolingIntakeTests(unittest.TestCase):
    def test_intake_sources_are_pinned_unique_and_non_authoritative(self):
        intake = load("config/external_repo_intake_2026-11-08.json")
        federation = load("config/external_repo_federation.json")
        self.assertEqual(intake["provided_repository_count"], 22)
        self.assertEqual(len(intake["sources"]), 22)
        names = [item["repo"].lower() for item in intake["sources"]]
        self.assertEqual(len(names), len(set(names)))
        registered = {item["repo"].lower(): item for item in federation["repositories"]}
        for item in intake["sources"]:
            self.assertRegex(item["head_commit"], r"^[0-9a-f]{40}$")
            self.assertTrue(item["source_url"].startswith("https://github.com/"))
            self.assertFalse(item["capital_authority"])
            self.assertIn(item["repo"].lower(), registered)
            source = registered[item["repo"].lower()]
            self.assertEqual(source["head_commit"], item["head_commit"])
            self.assertFalse(source["capital_authority"])
            self.assertEqual(source["mode"], item["mode"])

    def test_finance_skills_are_mirrored_to_supported_project_roots(self):
        for root in PROJECT_SKILL_ROOTS:
            for skill in SKILLS:
                path = ROOT / root / skill / "SKILL.md"
                self.assertTrue(path.is_file(), str(path))
                content = path.read_text(encoding="utf-8")
                self.assertIn("AURELIA applicability and authority boundary", content)
                self.assertIn("capital authority", content.lower())
                self.assertIn("Source provenance", content)

    def test_claude_project_agents_are_present_and_restricted(self):
        for agent in CLAUDE_AGENTS:
            path = ROOT / ".claude" / "agents" / f"{agent}.md"
            self.assertTrue(path.is_file(), str(path))
            content = path.read_text(encoding="utf-8")
            self.assertIn("capital authority", content.lower())
            self.assertIn("production secret", content.lower())

    def test_skill_and_plugin_inventories_reconcile(self):
        skills = load("config/agent_skill_inventory.json")
        plugins = load("config/agent_plugin_inventory.json")
        assignment = load("config/agent_tool_skill_assignment.json")
        matrix = load("config/agent_capability_matrix.json")
        self.assertEqual(skills["total_skills"], len(skills["items"]))
        self.assertEqual(plugins["total_skill_entries"], skills["total_skills"])
        self.assertEqual(plugins["plugin_groups"], len(plugins["plugins"]))
        plugin = next(
            item for item in plugins["plugins"]
            if item["plugin"] == "aurelia-curated-trading-research"
        )
        self.assertEqual(plugin["skill_count"], len(SKILLS))
        self.assertFalse(plugin["capital_authority"])
        for skill in SKILLS:
            uri = f"skills://plugins/aurelia-curated-trading-research/{skill}"
            item = next(record for record in skills["items"] if record["uri"] == uri)
            self.assertFalse(item["capital_authority"])
            self.assertEqual(set(item["assigned_agents"]), ASSIGNED_AGENTS)
        for agent in ASSIGNED_AGENTS:
            self.assertTrue(set(SKILLS).issubset(assignment["agents"][agent]["skills"]))
            self.assertTrue(set(SKILLS).issubset(matrix["agents"][agent]["skills"]))
        for agent in ("AURELIA", "Dev"):
            self.assertTrue(set(SKILLS).isdisjoint(assignment["agents"][agent]["skills"]))
            self.assertTrue(set(SKILLS).isdisjoint(matrix["agents"][agent]["skills"]))

    def test_live_execution_lock_is_unchanged_and_disabled(self):
        lock = (ROOT / "config" / "LIVE_LOCK.yaml").read_text(encoding="utf-8")
        self.assertIn("live_trading_enabled: false", lock)
        self.assertIn("FINAL_EXECUTION_AUTHORIZATION: false", lock)
        self.assertIn("LIVE_EXECUTION: BLOCKED", lock)

    def test_original_license_notices_are_preserved(self):
        for name in ("finance_skills-MIT.txt", "agency-agents-MIT.txt"):
            content = (ROOT / "third_party" / "licenses" / name).read_text(encoding="utf-8")
            self.assertIn("MIT License", content)
            self.assertIn("Permission is hereby granted", content)


if __name__ == "__main__":
    unittest.main()
