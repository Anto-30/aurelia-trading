from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = {
    "ClaudeCode",
    "KimiK3",
    "GrokBot",
    "GoogleAgentSkills",
    "GLM",
    "PlaywrightCLI",
    "AURELIA",
}


def load(path: str) -> dict:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(path)
    return value


def main() -> None:
    tools = load("config/agent_tool_inventory.json")
    skills = load("config/agent_skill_inventory.json")
    plugins = load("config/agent_plugin_inventory.json")
    matrix = load("config/agent_capability_matrix.json")
    boundary = load("config/agent_capability_boundary.json")
    continuity = load("config/agent_continuity_policy.json")
    lock = (ROOT / "config/LIVE_LOCK.yaml").read_text(encoding="utf-8")

    assert tools["total_tool_definitions"] > 0
    assert tools["total_provider_names"] == len(tools["providers"])

    seen_tools = 0
    for provider in tools["providers"]:
        assert provider["tool_count"] == len(provider["tools"]), provider["name"]
        assert provider["read_agents"], provider["name"]
        assert provider["blocked_capital_action"] is True, provider["name"]
        assert all(agent in AGENTS for agent in provider["read_agents"])
        assert all(agent in AGENTS for agent in provider["write_agents"])
        assert not set(provider["write_agents"]) - {"ClaudeCode"}
        seen_tools += provider["tool_count"]

    assert seen_tools == tools["total_tool_definitions"]

    assert skills["total_skills"] == len(skills["items"])
    for skill in skills["items"]:
        assert skill["uri"]
        assert skill["assigned_agents"]
        assert all(agent in AGENTS for agent in skill["assigned_agents"])
        assert skill["capital_authority"] is False

    assert plugins["plugin_groups"] == len(plugins["plugins"])
    assert plugins["total_skill_entries"] == skills["total_skills"]
    for plugin in plugins["plugins"]:
        assert plugin["assigned_agents"]
        assert all(agent in AGENTS for agent in plugin["assigned_agents"])
        assert plugin["capital_authority"] is False

    assert set(matrix["agents"]) == AGENTS
    assert boundary["capital_authority"] is False
    assert boundary["actors"]["AURELIA"]["capital_authority"] is True
    for name, actor in boundary["actors"].items():
        if name != "AURELIA":
            assert actor["capital_authority"] is False

    assert continuity["capital_authority"] is False
    assert continuity["heartbeat_seconds"] >= 900

    assert "live_trading_enabled: false" in lock
    assert "FINAL_EXECUTION_AUTHORIZATION: false" in lock
    assert "LIVE_EXECUTION: BLOCKED" in lock

    required_dirs = (
        ".claude/skills",
        ".grok/skills",
        ".agents/skills",
    )
    for path in required_dirs:
        assert (ROOT / path).is_dir(), path

    required_core = {
        "aurelia-continuity",
        "aurelia-federated-repair",
        "aurelia-evidence-reconciliation",
        "research-intelligence",
        "security-review",
        "browser-e2e",
        "ci-diagnostics",
        "evidence-inspection",
    }
    for root in required_dirs:
        names = {p.name for p in (ROOT / root).iterdir() if p.is_dir()}
        assert required_core <= names, root

    print("AGENT_INVENTORY_CHECK=PASS")
    print(f"TOOL_DEFINITIONS={tools['total_tool_definitions']}")
    print(f"TOOL_PROVIDERS={tools['total_provider_names']}")
    print(f"SKILL_ENTRIES={skills['total_skills']}")
    print(f"PLUGIN_GROUPS={plugins['plugin_groups']}")
    print("CAPITAL_AUTHORITY_EXTERNAL_AGENTS=FALSE")
    print("FINAL_EXECUTION_AUTHORIZATION=FALSE")
    print("LIVE_EXECUTION=BLOCKED")


if __name__ == "__main__":
    main()
