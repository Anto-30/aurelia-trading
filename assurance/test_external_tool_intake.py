# ruff: noqa: I001 -- import-only regression fixture; F/E rules remain enforced.
import json
import os
import re
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_text(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def _read_json(*parts):
    return json.loads(_read_text(*parts))


class ExternalToolIntakeTest(unittest.TestCase):
    def test_intake_has_exact_unique_repository_count_and_valid_pins(self):
        data = _read_json("config", "external_tool_intake_2026-11-09.json")
        repositories = data["repositories"]
        names = [item["repo"] for item in repositories]

        self.assertEqual(data["unique_repository_count"], 17)
        self.assertEqual(len(repositories), 17)
        self.assertEqual(len(set(names)), 17)
        self.assertEqual(sorted(names), sorted(set(names)))
        for item in repositories:
            self.assertRegex(item["head_commit"], re.compile(r"^[0-9a-f]{40}$"))
            self.assertTrue(item["url"].startswith("https://github.com/"))
            self.assertIn(
                item["mode"],
                {"REFERENCE_ONLY", "RESEARCH_ONLY", "SANDBOX_ONLY", "TOOLCHAIN_ONLY"},
            )
            self.assertIn("disposition", item)

    def test_repeated_qwen_repository_is_counted_once(self):
        data = _read_json("config", "external_tool_intake_2026-11-09.json")
        qwen = [item for item in data["repositories"] if item["repo"] == "QwenLM/qwen-code"]
        self.assertEqual(len(qwen), 1)
        self.assertEqual(qwen[0]["duplicate_supplied_url_occurrences"], 4)

    def test_intake_cannot_grant_capital_or_secret_access(self):
        data = _read_json("config", "external_tool_intake_2026-11-09.json")
        controls = data["global_controls"]
        self.assertFalse(controls["production_secret_access"])
        self.assertFalse(controls["broker_access"])
        self.assertFalse(controls["live_order_authority"])
        self.assertFalse(controls["capital_authority"])
        self.assertFalse(controls["live_lock_mutation"])
        self.assertFalse(controls["production_deployment_authority"])

    def test_claude_skills_exist_and_are_bound_to_agent_assignment(self):
        data = _read_json("config", "agent_tool_skill_assignment.json")
        skill_names = set(data["local_project_skills"])
        self.assertEqual(
            skill_names,
            {"aurelia-systematic-debugging", "aurelia-evidence-engineering"},
        )
        for skill in data["local_project_skills"].values():
            self.assertTrue(os.path.isfile(os.path.join(ROOT, skill["path"])))
            self.assertIn("ClaudeCode", skill["primary_agents"])
            self.assertIn("JEV", skill["independent_reviewers"])

        inventory = _read_json("config", "agent_skill_inventory.json")
        registered = {item["uri"] for item in inventory["items"]}
        for skill in data["local_project_skills"].values():
            self.assertIn(f"repo://{skill['path']}", registered)

    def test_ruff_is_development_only_and_version_pinned(self):
        pyproject = _read_text("pyproject.toml")
        dependencies = pyproject.split("[project.optional-dependencies]", 1)[0]
        dev_section = pyproject.split("dev = [", 1)[1].split("]", 1)[0]
        self.assertNotIn("ruff", dependencies)
        self.assertIn("ruff==0.17.4", dev_section)


if __name__ == "__main__":
    unittest.main()
