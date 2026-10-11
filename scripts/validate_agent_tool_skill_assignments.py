from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict:
    with (ROOT / relative).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise AssertionError(f"{relative}: expected JSON object")
    return value


def main() -> None:
    assignment = load_json("config/agent_tool_skill_assignment.json")
    matrix = load_json("config/agent_capability_matrix.json")
    router = load_json("config/repo_agent_routing.json")
    boundary = load_json("config/agent_capability_boundary.json")
    tool_inventory = load_json("config/agent_tool_inventory.json")
    skill_inventory = load_json("config/agent_skill_inventory.json")
    repo_registry = load_json("config/external_repo_federation.json")
    skill_registry = load_json("config/agent_skill_federation.json")
    intake = load_json("config/external_repo_intake_2026-10-11.json")

    assert assignment["schema"] == "aurelia.agent_tool_skill_assignment.v1"
    assert assignment["authority_model"]["canonical_repository"] == "Anto-30/aurelia-trading"
    assert assignment["authority_model"]["external_agents_capital_authority"] is False
    assert assignment["runtime_connection_snapshot"]["desktop_commander_device_count"] == 0
    assert assignment["runtime_connection_snapshot"]["dev_runtime"] == "NOT_CONNECTED"

    profiles = assignment["agents"]
    canonical = set(profiles)
    assert canonical == set(matrix["agents"]), "assignment and capability-matrix agents differ"
    assert canonical.issubset(router["agents"]), "one or more assigned agents missing from repo routing"
    assert canonical.issubset(boundary["actors"]), "one or more assigned agents missing from capability boundary"

    for name, profile in profiles.items():
        assert profile.get("role") and profile.get("tools") and profile.get("skills") is not None, name
        assert profile.get("can_mutate_live_lock") is False, name
        if name != "AURELIA":
            assert profile.get("capital_authority") is False, name
        else:
            assert profile.get("capital_authority") is True
    assert profiles["Dev"]["status"] == "NOT_CONNECTED"
    assert router["agents"]["Dev"]["runtime_status"] == "NOT_CONNECTED"
    assert boundary["actors"]["ChatGPT"]["capital_authority"] is False
    assert boundary["actors"]["Dev"]["capital_authority"] is False

    known_plugins = {item.get("plugin") for item in skill_inventory.get("items", [])}
    for name, profile in profiles.items():
        for plugin in profile.get("plugins", []):
            plugin_id = plugin.split()[0].split("(")[0]
            assert plugin_id in known_plugins, (name, plugin, "plugin absent from skill inventory")
    for route in assignment.get("task_routes", []):
        assert route["primary"] in canonical, route
        assert set(route.get("reviewers", [])).issubset(canonical), route
        for plugin in route.get("plugins", []):
            plugin_id = plugin.split()[0].split("(")[0]
            assert plugin_id in known_plugins, (route.get("task"), plugin)

    permitted_modes = {"RESEARCH_ONLY", "SANDBOX_ONLY", "TOOLCHAIN_ONLY", "REFERENCE_ONLY"}
    repo_by_name = {item["repo"]: item for item in repo_registry["repositories"]}
    assert len(repo_by_name) == len(repo_registry["repositories"]), "duplicate external repo registry entry"
    assert len({key.lower() for key in repo_by_name}) == len(repo_by_name), "case-insensitive external repo duplicate"
    assert len({item["name"] for item in skill_registry["sources"]}) == len(skill_registry["sources"]), "duplicate skill source name"

    intake_sources = intake.get("sources", [])
    assert len(intake_sources) == intake["provided_repository_count"] == 84
    intake_names = {item["repo"] for item in intake_sources}
    assert len(intake_names) == len(intake_sources), "duplicate repository in intake manifest"
    for item in intake_sources:
        assert re.fullmatch(r"[0-9a-f]{40}", item["head_commit"]), (item["repo"], item["head_commit"])
        assert item["source_url"].startswith("https://github.com/")
        assert item["mode"] in permitted_modes
        assert item.get("capital_authority", False) is False
        assert item.get("security_review_status") == "PENDING"
        assert item.get("physical_runtime_install") == "NOT_CLAIMED"
        assert item["assigned_agents"] and set(item["assigned_agents"]).issubset(router["agents"]), item["repo"]
        registered = repo_by_name[item["repo"]]
        assert registered["head_commit"] == item["head_commit"], item["repo"]
        assert registered["assigned_agents"] == item["assigned_agents"], item["repo"]
        assert registered["mode"] == item["mode"], item["repo"]
        assert registered.get("capital_authority", False) is False, item["repo"]

    assert repo_registry["global_controls"]["capital_authority"] is False
    assert repo_registry["global_controls"]["live_order_submission"] is False
    assert repo_registry["global_controls"]["live_lock_mutation"] is False
    assert repo_registry["global_controls"]["secret_reading"] is False
    assert repo_registry["global_controls"]["external_code_execution"] == "DENY_BY_DEFAULT"
    assert skill_registry["default_policy"]["capital_authority"] is False
    assert skill_registry["default_policy"]["live_order_authority"] is False
    assert tool_inventory["total_provider_names"] > 0
    assert skill_inventory["total_skills"] > 0
    print("AGENT_TOOL_SKILL_ASSIGNMENT_AUDIT=PASS")
    print(f"AGENT_PROFILES={len(profiles)}")
    print(f"INTAKE_REPOSITORIES={len(intake_sources)}")
    print(f"REGISTERED_EXTERNAL_REPOSITORIES={len(repo_registry['repositories'])}")
    print(f"REGISTERED_SKILL_SOURCES={len(skill_registry['sources'])}")
    print("DEV_RUNTIME=NOT_CONNECTED")
    print("CAPITAL_AUTHORITY=RESTRICTED_TO_EXISTING_AURELIA_CONTROL_PLANE")
    print("LIVE_EXECUTION=UNCHANGED_BY_THIS_POLICY")


if __name__ == "__main__":
    main()
