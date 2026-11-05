from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class ClaudeCeoGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.assignment = load("config/agent_tool_skill_assignment.json")
        cls.boundary = load("config/agent_capability_boundary.json")
        cls.matrix = load("config/agent_capability_matrix.json")
        cls.routing = load("config/repo_agent_routing.json")

    def test_claude_code_is_primary_executive_and_orchestration_agent(self) -> None:
        model = self.assignment["authority_model"]
        governance = self.assignment["executive_governance"]
        self.assertEqual(model["primary_executive_agent"], "ClaudeCode")
        self.assertEqual(model["primary_orchestration_agent"], "ClaudeCode")
        self.assertEqual(governance["executive_agent"], "ClaudeCode")
        self.assertEqual(governance["role"], "AURELIA CEO / Chief Executive Orchestrator")
        self.assertIn("CEO", self.assignment["agents"]["ClaudeCode"]["role"])

    def test_grok_remains_specialist_orchestration_support(self) -> None:
        model = self.assignment["authority_model"]
        self.assertEqual(model["specialist_orchestration_support_agent"], "GrokBot")
        routes = self.assignment["task_routes"]
        route = next(x for x in routes if x["task"] == "Agent orchestration, harnesses, worker/agent memory")
        self.assertEqual(route["primary"], "ClaudeCode")
        self.assertIn("GrokBot", route["reviewers"])

    def test_ceo_delegation_requires_registered_verified_workers(self) -> None:
        governance = self.assignment["executive_governance"]
        self.assertTrue(governance["require_registered_agent"])
        self.assertTrue(governance["require_active_worker_lease"])
        self.assertIn("JEV", governance["delegation_targets"])
        self.assertIn("KimiK3", governance["delegation_targets"])
        self.assertIn("GoogleAgentSkills", governance["delegation_targets"])
        self.assertIn("PlaywrightCLI", governance["delegation_targets"])

    def test_external_runtimes_are_not_claimed_connected(self) -> None:
        governance = self.assignment["executive_governance"]
        statuses = {x["name"]: x["status"] for x in governance["external_runtime_interfaces"]}
        for name in ("OpenClaw", "Cursor IDE", "Codex", "DeepSeek Harness", "Hermes"):
            self.assertEqual(statuses[name], "NOT_CONNECTED")

    def test_claude_ceo_remains_non_capital_and_cannot_mutate_live_lock(self) -> None:
        profile = self.assignment["agents"]["ClaudeCode"]
        actor = self.boundary["actors"]["ClaudeCode"]
        self.assertIs(profile["capital_authority"], False)
        self.assertIs(profile["can_mutate_live_lock"], False)
        self.assertIs(actor["capital_authority"], False)
        for forbidden in ("authorize_capital", "submit_orders", "flip_live_lock"):
            self.assertIn(forbidden, actor["may_not"])
        self.assertIn("delegate_registered_agent_tasks", actor["may"])

    def test_aurelia_remains_the_only_capital_control_plane(self) -> None:
        model = self.assignment["authority_model"]
        self.assertEqual(model["sole_capital_control_plane"], "AURELIA")
        self.assertIs(self.boundary["actors"]["AURELIA"]["capital_authority"], True)
        self.assertEqual(self.matrix["agents"]["AURELIA"]["authority"], "capital plane only; subject to deterministic controls")

    def test_material_code_changes_keep_independent_reviewers(self) -> None:
        route = next(x for x in self.assignment["task_routes"] if x["task"] == "AURELIA code implementation and repair")
        self.assertIn("JEV", route["reviewers"])
        self.assertIn("ChatGPT", route["reviewers"])
        self.assertTrue(self.assignment["executive_governance"]["ceo_may_self_approve_material_changes"] is False)


if __name__ == "__main__":
    unittest.main()
