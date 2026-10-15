from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]



def require(condition, message=None, *, location=""):
    """Enforce a runtime invariant even when Python optimization is enabled."""
    if not condition:
        detail = message if message is not None else "validation condition failed"
        prefix = f"{location}: " if location else ""
        raise AssertionError(f"{prefix}{detail}")

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

    require(
        assignment["schema"] == "aurelia.agent_tool_skill_assignment.v1",
        location="scripts/validate_agent_tool_skill_assignments.py:29",
    )
    require(
        assignment["authority_model"]["canonical_repository"] == "Anto-30/aurelia-trading",
        location="scripts/validate_agent_tool_skill_assignments.py:30",
    )
    require(
        assignment["authority_model"]["external_agents_capital_authority"] is False,
        location="scripts/validate_agent_tool_skill_assignments.py:31",
    )
    require(
        assignment["runtime_connection_snapshot"]["desktop_commander_device_count"] == 0,
        location="scripts/validate_agent_tool_skill_assignments.py:32",
    )
    require(
        assignment["runtime_connection_snapshot"]["dev_runtime"] == "NOT_CONNECTED",
        location="scripts/validate_agent_tool_skill_assignments.py:33",
    )

    profiles = assignment["agents"]
    canonical = set(profiles)
    require(
        canonical == set(matrix["agents"]),
        "assignment and capability-matrix agents differ",
        location="scripts/validate_agent_tool_skill_assignments.py:37",
    )
    require(
        canonical.issubset(router["agents"]),
        "one or more assigned agents missing from repo routing",
        location="scripts/validate_agent_tool_skill_assignments.py:38",
    )
    require(
        canonical.issubset(boundary["actors"]),
        "one or more assigned agents missing from capability boundary",
        location="scripts/validate_agent_tool_skill_assignments.py:39",
    )

    for name, profile in profiles.items():
        require(
            profile.get("role") and profile.get("tools") and profile.get("skills") is not None,
            name,
            location="scripts/validate_agent_tool_skill_assignments.py:42",
        )
        require(
            profile.get("can_mutate_live_lock") is False,
            name,
            location="scripts/validate_agent_tool_skill_assignments.py:43",
        )
        if name != "AURELIA":
            require(
                profile.get("capital_authority") is False,
                name,
                location="scripts/validate_agent_tool_skill_assignments.py:45",
            )
        else:
            require(
                profile.get("capital_authority") is True,
                location="scripts/validate_agent_tool_skill_assignments.py:47",
            )
    require(
        profiles["Dev"]["status"] == "NOT_CONNECTED",
        location="scripts/validate_agent_tool_skill_assignments.py:48",
    )
    require(
        router["agents"]["Dev"]["runtime_status"] == "NOT_CONNECTED",
        location="scripts/validate_agent_tool_skill_assignments.py:49",
    )
    require(
        boundary["actors"]["ChatGPT"]["capital_authority"] is False,
        location="scripts/validate_agent_tool_skill_assignments.py:50",
    )
    require(
        boundary["actors"]["Dev"]["capital_authority"] is False,
        location="scripts/validate_agent_tool_skill_assignments.py:51",
    )

    known_plugins = {item.get("plugin") for item in skill_inventory.get("items", [])}
    for name, profile in profiles.items():
        for plugin in profile.get("plugins", []):
            plugin_id = plugin.split()[0].split("(")[0]
            require(
                plugin_id in known_plugins,
                (name, plugin, "plugin absent from skill inventory"),
                location="scripts/validate_agent_tool_skill_assignments.py:57",
            )
    for route in assignment.get("task_routes", []):
        require(
            route["primary"] in canonical,
            route,
            location="scripts/validate_agent_tool_skill_assignments.py:59",
        )
        require(
            set(route.get("reviewers", [])).issubset(canonical),
            route,
            location="scripts/validate_agent_tool_skill_assignments.py:60",
        )
        for plugin in route.get("plugins", []):
            plugin_id = plugin.split()[0].split("(")[0]
            require(
                plugin_id in known_plugins,
                (route.get("task"), plugin),
                location="scripts/validate_agent_tool_skill_assignments.py:63",
            )

    permitted_modes = {"RESEARCH_ONLY", "SANDBOX_ONLY", "TOOLCHAIN_ONLY", "REFERENCE_ONLY"}
    repo_by_name = {item["repo"]: item for item in repo_registry["repositories"]}
    require(
        len(repo_by_name) == len(repo_registry["repositories"]),
        "duplicate external repo registry entry",
        location="scripts/validate_agent_tool_skill_assignments.py:67",
    )
    require(
        len({key.lower() for key in repo_by_name}) == len(repo_by_name),
        "case-insensitive external repo duplicate",
        location="scripts/validate_agent_tool_skill_assignments.py:68",
    )
    require(
        len({item["name"] for item in skill_registry["sources"]}) == len(skill_registry["sources"]),
        "duplicate skill source name",
        location="scripts/validate_agent_tool_skill_assignments.py:69",
    )

    intake_sources = intake.get("sources", [])
    require(
        len(intake_sources) == intake["provided_repository_count"] == 84,
        location="scripts/validate_agent_tool_skill_assignments.py:72",
    )
    intake_names = {item["repo"] for item in intake_sources}
    require(
        len(intake_names) == len(intake_sources),
        "duplicate repository in intake manifest",
        location="scripts/validate_agent_tool_skill_assignments.py:74",
    )
    for item in intake_sources:
        require(
            re.fullmatch(r"[0-9a-f]{40}", item["head_commit"]),
            (item["repo"], item["head_commit"]),
            location="scripts/validate_agent_tool_skill_assignments.py:76",
        )
        require(
            item["source_url"].startswith("https://github.com/"),
            location="scripts/validate_agent_tool_skill_assignments.py:77",
        )
        require(
            item["mode"] in permitted_modes,
            location="scripts/validate_agent_tool_skill_assignments.py:78",
        )
        require(
            item.get("capital_authority", False) is False,
            location="scripts/validate_agent_tool_skill_assignments.py:79",
        )
        require(
            item.get("security_review_status") == "PENDING",
            location="scripts/validate_agent_tool_skill_assignments.py:80",
        )
        require(
            item.get("physical_runtime_install") == "NOT_CLAIMED",
            location="scripts/validate_agent_tool_skill_assignments.py:81",
        )
        require(
            item["assigned_agents"] and set(item["assigned_agents"]).issubset(router["agents"]),
            item["repo"],
            location="scripts/validate_agent_tool_skill_assignments.py:82",
        )
        registered = repo_by_name[item["repo"]]
        require(
            registered["head_commit"] == item["head_commit"],
            item["repo"],
            location="scripts/validate_agent_tool_skill_assignments.py:84",
        )
        require(
            registered["assigned_agents"] == item["assigned_agents"],
            item["repo"],
            location="scripts/validate_agent_tool_skill_assignments.py:85",
        )
        require(
            registered["mode"] == item["mode"],
            item["repo"],
            location="scripts/validate_agent_tool_skill_assignments.py:86",
        )
        require(
            registered.get("capital_authority", False) is False,
            item["repo"],
            location="scripts/validate_agent_tool_skill_assignments.py:87",
        )

    require(
        repo_registry["global_controls"]["capital_authority"] is False,
        location="scripts/validate_agent_tool_skill_assignments.py:89",
    )
    require(
        repo_registry["global_controls"]["live_order_submission"] is False,
        location="scripts/validate_agent_tool_skill_assignments.py:90",
    )
    require(
        repo_registry["global_controls"]["live_lock_mutation"] is False,
        location="scripts/validate_agent_tool_skill_assignments.py:91",
    )
    require(
        repo_registry["global_controls"]["secret_reading"] is False,
        location="scripts/validate_agent_tool_skill_assignments.py:92",
    )
    require(
        repo_registry["global_controls"]["external_code_execution"] == "DENY_BY_DEFAULT",
        location="scripts/validate_agent_tool_skill_assignments.py:93",
    )
    require(
        skill_registry["default_policy"]["capital_authority"] is False,
        location="scripts/validate_agent_tool_skill_assignments.py:94",
    )
    require(
        skill_registry["default_policy"]["live_order_authority"] is False,
        location="scripts/validate_agent_tool_skill_assignments.py:95",
    )
    require(
        tool_inventory["total_provider_names"] > 0,
        location="scripts/validate_agent_tool_skill_assignments.py:96",
    )
    require(
        skill_inventory["total_skills"] > 0,
        location="scripts/validate_agent_tool_skill_assignments.py:97",
    )
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
