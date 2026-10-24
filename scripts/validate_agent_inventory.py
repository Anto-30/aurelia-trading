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


def load(path: str) -> dict:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(path)
    return value


def validate_agent_remediation_backlog(
    backlog: dict, delegation: dict, known_agents: set[str]
) -> None:
    """Validate backlog schema and cross-references before treating it as actionable."""
    assert backlog.get("schema") == "aurelia.agent_remediation_backlog.v1"
    assert backlog.get("canonical_repository") == "https://github.com/Anto-30/aurelia-trading"

    authority = backlog.get("authority_model", {})
    constraints = authority.get("constraints")
    assert isinstance(constraints, list) and all(isinstance(x, str) and x.strip() for x in constraints)
    constraint_text = " ".join(constraints).lower()
    assert "external agents have no capital authority" in constraint_text
    assert "do not change live_lock to force release" in constraint_text
    assert "no merge/deploy/promotion claim without observed platform result and required review" in constraint_text
    continuous_claim = authority.get("continuous_operation_claim", "")
    assert isinstance(continuous_claim, str) and continuous_claim.startswith("NOT_VERIFIED")

    status_legend = backlog.get("status_legend")
    assert isinstance(status_legend, dict) and status_legend
    allowed_statuses = set(status_legend)
    streams = backlog.get("workstreams")
    assert isinstance(streams, list) and streams

    required_fields = {
        "id", "priority", "status", "title", "finding", "owner",
        "collaborators", "dependencies", "external_prerequisites",
        "acceptance_criteria", "evidence_path",
    }
    stream_by_id = {}
    for index, stream in enumerate(streams):
        assert isinstance(stream, dict), f"workstream[{index}] must be an object"
        missing = required_fields - set(stream)
        assert not missing, f"workstream[{index}] missing fields: {sorted(missing)}"
        stream_id = stream.get("id")
        assert isinstance(stream_id, str) and stream_id.strip(), f"workstream[{index}] missing id"
        assert stream_id not in stream_by_id, f"duplicate workstream id: {stream_id}"
        stream_by_id[stream_id] = stream
        assert stream.get("priority") in {"P0", "P1", "P2"}, stream_id
        assert stream.get("status") in allowed_statuses, (stream_id, stream.get("status"))
        for field in ("title", "finding", "evidence_path"):
            assert isinstance(stream.get(field), str) and stream[field].strip(), (stream_id, field)
        assert stream["evidence_path"].startswith("artifacts/"), (stream_id, stream["evidence_path"])
        assert isinstance(stream.get("owner"), str) and stream["owner"] in known_agents, (
            stream_id, stream.get("owner")
        )
        collaborators = stream.get("collaborators")
        assert isinstance(collaborators, list) and collaborators, stream_id
        assert all(isinstance(agent, str) and agent in known_agents for agent in collaborators), stream_id
        acceptance = stream.get("acceptance_criteria")
        assert isinstance(acceptance, list) and acceptance, stream_id
        assert all(isinstance(item, str) and item.strip() for item in acceptance), stream_id

        dependencies = stream.get("dependencies")
        assert isinstance(dependencies, list), f"{stream_id}: dependencies must be a list"
        assert all(isinstance(dep, str) and dep.strip() for dep in dependencies), stream_id
        assert len(dependencies) == len(set(dependencies)), f"{stream_id}: duplicate dependency"
        assert stream_id not in dependencies, f"{stream_id}: self-dependency is forbidden"
        for dependency in dependencies:
            assert dependency in {x.get("id") for x in streams}, (
                stream_id, f"dangling dependency reference: {dependency}"
            )

        prerequisites = stream.get("external_prerequisites")
        assert isinstance(prerequisites, list), (
            f"{stream_id}: external_prerequisites must be a list"
        )
        assert all(isinstance(item, str) and item.strip() for item in prerequisites), stream_id

    # Dependencies form a directed acyclic graph; otherwise no workstream order is satisfiable.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stream_id: str) -> None:
        if stream_id in visiting:
            raise AssertionError(f"workstream dependency cycle detected at {stream_id}")
        if stream_id in visited:
            return
        visiting.add(stream_id)
        for dependency in stream_by_id[stream_id]["dependencies"]:
            visit(dependency)
        visiting.remove(stream_id)
        visited.add(stream_id)

    for stream_id in stream_by_id:
        visit(stream_id)

    tasks = delegation.get("tasks")
    assert isinstance(tasks, list) and tasks
    task_agents = [task.get("agent") for task in tasks]
    assert len(task_agents) == len(set(task_agents)), "duplicate delegation task agent"
    assert set(task_agents) == known_agents, "backlog task ownership must cover the registered agent set"

    assigned_streams: set[str] = set()
    for task in tasks:
        ids = task.get("workstream_ids")
        assert isinstance(ids, list) and ids, f"{task.get('agent')}: workstream_ids required"
        assert len(ids) == len(set(ids)), f"{task.get('agent')}: duplicate workstream assignment"
        for stream_id in ids:
            assert stream_id in stream_by_id, (task.get("agent"), f"unknown workstream id: {stream_id}")
            assigned_streams.add(stream_id)
    assert assigned_streams == set(stream_by_id), (
        f"orphan workstreams: {sorted(set(stream_by_id) - assigned_streams)}"
    )


def main() -> None:
    tools = load("config/agent_tool_inventory.json")
    skills = load("config/agent_skill_inventory.json")
    plugins = load("config/agent_plugin_inventory.json")
    matrix = load("config/agent_capability_matrix.json")
    boundary = load("config/agent_capability_boundary.json")
    continuity = load("config/agent_continuity_policy.json")
    delegation = load("config/agent_delegation_tasks.json")
    remediation_backlog = load("config/agent_remediation_backlog.json")
    validate_agent_remediation_backlog(remediation_backlog, delegation, AGENTS)
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
        assert not set(provider["write_agents"]) - {"ClaudeCode", "GrokBot"}
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
    assert delegation["schema"] == "aurelia.agent_delegation_tasks.v1"
    tasks = delegation["tasks"]
    assert isinstance(tasks, list) and tasks
    task_agents = [task["agent"] for task in tasks]
    assert set(task_agents) == AGENTS
    assert len(task_agents) == len(set(task_agents))
    for task in tasks:
        assert task["task_id"]
        assert task["objective"]
        assert task["acceptance_criteria"]
        assert task["evidence_path"]
        assert task["status"] in {"assigned", "running", "completed", "blocked"}
        assert task["runtime_proof"]["required_event"] == "subagent.started"
        assert task["runtime_proof"]["execution_proof"] is False
    assert delegation["execution_proof_policy"]["configuration_is_not_execution"] is True
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
    print("DELEGATED_TASK_ASSIGNMENTS=PASS")
    print("RUNTIME_EXECUTION_PROOF=REQUIRED")


if __name__ == "__main__":
    main()
