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
    "JEV",
    "AURELIA",
    "ChatGPT",
    "Dev",
}



def require(condition, message=None, *, location=""):
    """Enforce a runtime invariant even when Python optimization is enabled."""
    if not condition:
        detail = message if message is not None else "validation condition failed"
        prefix = f"{location}: " if location else ""
        raise AssertionError(f"{prefix}{detail}")

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
    delegation = load("config/agent_delegation_tasks.json")
    lock = (ROOT / "config/LIVE_LOCK.yaml").read_text(encoding="utf-8")

    require(
        tools["total_tool_definitions"] > 0,
        location="scripts/validate_agent_inventory.py:38",
    )
    require(
        tools["total_provider_names"] == len(tools["providers"]),
        location="scripts/validate_agent_inventory.py:39",
    )

    seen_tools = 0
    for provider in tools["providers"]:
        require(
            provider["tool_count"] == len(provider["tools"]),
            provider["name"],
            location="scripts/validate_agent_inventory.py:43",
        )
        require(
            provider["read_agents"],
            provider["name"],
            location="scripts/validate_agent_inventory.py:44",
        )
        require(
            provider["blocked_capital_action"] is True,
            provider["name"],
            location="scripts/validate_agent_inventory.py:45",
        )
        require(
            all(agent in AGENTS for agent in provider["read_agents"]),
            location="scripts/validate_agent_inventory.py:46",
        )
        require(
            all(agent in AGENTS for agent in provider["write_agents"]),
            location="scripts/validate_agent_inventory.py:47",
        )
        require(
            not set(provider["write_agents"]) - {"ClaudeCode", "GrokBot"},
            location="scripts/validate_agent_inventory.py:48",
        )
        seen_tools += provider["tool_count"]

    require(
        seen_tools == tools["total_tool_definitions"],
        location="scripts/validate_agent_inventory.py:51",
    )

    require(
        skills["total_skills"] == len(skills["items"]),
        location="scripts/validate_agent_inventory.py:53",
    )
    for skill in skills["items"]:
        require(
            skill["uri"],
            location="scripts/validate_agent_inventory.py:55",
        )
        require(
            skill["assigned_agents"],
            location="scripts/validate_agent_inventory.py:56",
        )
        require(
            all(agent in AGENTS for agent in skill["assigned_agents"]),
            location="scripts/validate_agent_inventory.py:57",
        )
        require(
            skill["capital_authority"] is False,
            location="scripts/validate_agent_inventory.py:58",
        )

    require(
        plugins["plugin_groups"] == len(plugins["plugins"]),
        location="scripts/validate_agent_inventory.py:60",
    )
    require(
        plugins["total_skill_entries"] == skills["total_skills"],
        location="scripts/validate_agent_inventory.py:61",
    )
    for plugin in plugins["plugins"]:
        require(
            plugin["assigned_agents"],
            location="scripts/validate_agent_inventory.py:63",
        )
        require(
            all(agent in AGENTS for agent in plugin["assigned_agents"]),
            location="scripts/validate_agent_inventory.py:64",
        )
        require(
            plugin["capital_authority"] is False,
            location="scripts/validate_agent_inventory.py:65",
        )

    require(
        set(matrix["agents"]) == AGENTS,
        location="scripts/validate_agent_inventory.py:67",
    )
    require(
        delegation["schema"] == "aurelia.agent_delegation_tasks.v1",
        location="scripts/validate_agent_inventory.py:68",
    )
    tasks = delegation["tasks"]
    require(
        isinstance(tasks, list) and tasks,
        location="scripts/validate_agent_inventory.py:70",
    )
    task_agents = [task["agent"] for task in tasks]
    require(
        set(task_agents) == AGENTS,
        location="scripts/validate_agent_inventory.py:72",
    )
    require(
        len(task_agents) == len(set(task_agents)),
        location="scripts/validate_agent_inventory.py:73",
    )
    for task in tasks:
        require(
            task["task_id"],
            location="scripts/validate_agent_inventory.py:75",
        )
        require(
            task["objective"],
            location="scripts/validate_agent_inventory.py:76",
        )
        require(
            task["acceptance_criteria"],
            location="scripts/validate_agent_inventory.py:77",
        )
        require(
            task["evidence_path"],
            location="scripts/validate_agent_inventory.py:78",
        )
        require(
            task["status"] in {"assigned", "running", "completed", "blocked"},
            location="scripts/validate_agent_inventory.py:79",
        )
        require(
            task["runtime_proof"]["required_event"] == "subagent.started",
            location="scripts/validate_agent_inventory.py:80",
        )
        require(
            task["runtime_proof"]["execution_proof"] is False,
            location="scripts/validate_agent_inventory.py:81",
        )
    require(
        delegation["execution_proof_policy"]["configuration_is_not_execution"] is True,
        location="scripts/validate_agent_inventory.py:82",
    )
    require(
        boundary["capital_authority"] is False,
        location="scripts/validate_agent_inventory.py:83",
    )
    require(
        boundary["actors"]["AURELIA"]["capital_authority"] is True,
        location="scripts/validate_agent_inventory.py:84",
    )
    for name, actor in boundary["actors"].items():
        if name != "AURELIA":
            require(
                actor["capital_authority"] is False,
                location="scripts/validate_agent_inventory.py:87",
            )

    require(
        continuity["capital_authority"] is False,
        location="scripts/validate_agent_inventory.py:89",
    )
    require(
        continuity["heartbeat_seconds"] >= 900,
        location="scripts/validate_agent_inventory.py:90",
    )

    require(
        "live_trading_enabled: false" in lock,
        location="scripts/validate_agent_inventory.py:92",
    )
    require(
        "FINAL_EXECUTION_AUTHORIZATION: false" in lock,
        location="scripts/validate_agent_inventory.py:93",
    )
    require(
        "LIVE_EXECUTION: BLOCKED" in lock,
        location="scripts/validate_agent_inventory.py:94",
    )

    required_dirs = (
        ".claude/skills",
        ".grok/skills",
        ".agents/skills",
    )
    for path in required_dirs:
        require(
            (ROOT / path).is_dir(),
            path,
            location="scripts/validate_agent_inventory.py:102",
        )

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
        require(
            required_core <= names,
            root,
            location="scripts/validate_agent_inventory.py:116",
        )

    print("AGENT_INVENTORY_CHECK=PASS")
    print(f"TOOL_DEFINITIONS={tools['total_tool_definitions']}")
    print(f"TOOL_PROVIDERS={tools['total_provider_names']}")
    print(f"SKILL_ENTRIES={skills['total_skills']}")
    print(f"PLUGIN_GROUPS={plugins['plugin_groups']}")
    print("CAPITAL_AUTHORITY_EXTERNAL_AGENTS=FALSE")
    print("FINAL_EXECUTION_AUTHORIZATION=FALSE")
    print("LIVE_EXECUTION=BLOCKED")
    print("DELEGATED_TASK_ASSIGNMENTS=PASS")
    print("RUNTIME_EXECUTION_PROOF=REQUIRED")


if __name__ == "__main__":
    main()
