from __future__ import annotations

import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
AGENTS = {
    "ClaudeCode", "KimiK3", "GrokBot", "GoogleAgentSkills", "GLM",
    "PlaywrightCLI", "JEV", "AURELIA", "ChatGPT", "Dev",
}
EXPECTED = {
    "can1357/oh-my-pi": "96e4d8eb5ba1212d2d6018f242de266284cffab9",
    "ethereum-lists/chains": "e17474286275730fb6b0490b1d7ea1c64a36ed9e",
    "open-metadata/OpenMetadata": "a3012259ca604141e3f778aa3f259d827371470a",
    "drewnoakes/metadata-extractor": "4d5cd46935c1987d8b19bfb49f3a24eb1d832e53",
    "ronmamo/reflections": "f5514b125c4f4b58e92beb0979a40ddce48d5be1",
    "microsoft/reflect-metadata": "acdeee445509ea05c8fab270f73928f7bb2c50f1",
    "apache/ossie": "172a3e566f2fc9c0a733ebbb470e97c33d2bd8b1",
    "grafeas/grafeas": "4a8bf366a01f0e509b9118b9f8afd64f211e64c6",
    "docker/metadata-action": "1ec73021df0717d8bef7700a897c064453280439",
    "google/ml-metadata": "7efdb25a3390cd1547372792ece6390e5b4364d1",
    "microsoft/win32metadata": "ae66c067ff3e9516fcc9cda09204bf72a9d57e56",
    "drewnoakes/metadata-extractor-dotnet": "cb71a8ad84a15dbf64ddb25a77c17cd855adfef4",
    "macbre/sql-metadata": "e48f1595cffaf409cef51fe1dfff21519da36ee5",
    "berachain/metadata": "1cd819a51e50ec2d603f2409f382232c99ec1de0",
    "Exiv2/exiv2": "ef4e79590c53cdef48bbed5629cdb81065b42287",
    "icsharpcode/ILSpy": "695f7aced9626eb5bffdf9a04a835cd984b9b5ce",
    "jekyll/github-metadata": "c26a5d4574785fa79ecbccc1df890f3f9909a02d",
    "OpenLineage/OpenLineage": "dd64b09365f08ee02a3a0653ddda0e62d8cc76f2",
    "dependabot/fetch-metadata": "57721ba1e64f4a53fe9300b820eeee8398b772fb",
}


def load(path: str) -> dict:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path}: expected object")
    return value


def main() -> None:
    repos = load("config/external_repo_federation.json")["repositories"]
    by_name = {item["repo"]: item for item in repos}
    assert len(by_name) == len(repos), "duplicate external repository entries"
    assert set(EXPECTED).issubset(by_name), "one or more requested repositories are missing"
    for name, commit in EXPECTED.items():
        item = by_name[name]
        assert item["head_commit"] == commit, (name, "commit pin drift")
        assert re.fullmatch(r"[0-9a-f]{40}", item["head_commit"]), name
        assert item["source_url"] == f"https://github.com/{name}", name
        assert item["assigned_agents"] and set(item["assigned_agents"]).issubset(AGENTS), name
        assert item["capital_authority"] is False, name
        assert item["runtime_dependency"] is False, name
        assert item["runtime_install"] == "NOT_INSTALLED", name
        assert item["integration_status"] == "PINNED_REFERENCE_ONLY", name
        assert item["license"], (name, "missing licence metadata")
        assert item["mode"] in {"REFERENCE_ONLY", "TOOLCHAIN_ONLY", "SANDBOX_ONLY"}, name

    matrix = load("config/agent_capability_matrix.json")
    assignment = load("config/agent_tool_skill_assignment.json")
    router = load("config/repo_agent_routing.json")
    inventory = load("config/agent_skill_inventory.json")
    plugins = load("config/agent_plugin_inventory.json")
    federation = load("config/agent_skill_federation.json")
    uri = "skills://aurelia/metadata-provenance"

    assert set(matrix["agents"]) == AGENTS
    assert set(assignment["agents"]) == AGENTS
    for agent in AGENTS:
        assert "metadata-provenance" in matrix["agents"][agent]["skills"], agent
        assert "metadata-provenance" in assignment["agents"][agent]["skills"], agent
        assert "metadata-provenance" in router["agents"][agent].get("skills", []), agent

    skill_items = [item for item in inventory["items"] if item.get("uri") == uri]
    assert len(skill_items) == 1
    assert set(skill_items[0]["assigned_agents"]) == AGENTS
    assert skill_items[0]["capital_authority"] is False
    assert skill_items[0]["plugin"] == "aurelia-internal-skills"
    assert inventory["total_skills"] == len(inventory["items"])

    plugin_items = [item for item in plugins["plugins"] if item.get("plugin") == "aurelia-internal-skills"]
    assert len(plugin_items) == 1
    assert plugin_items[0]["skill_uris"] == [uri]
    assert plugin_items[0]["capital_authority"] is False
    assert plugins["total_skill_entries"] == inventory["total_skills"]
    assert plugins["plugin_groups"] == len(plugins["plugins"])

    sources = [item for item in federation["sources"] if item.get("name") == "aurelia-metadata-provenance"]
    assert len(sources) == 1
    assert set(sources[0]["assigned_agents"]) == AGENTS
    assert sources[0]["capital_authority"] is False
    assert re.fullmatch(r"[0-9a-f]{40}", sources[0]["pinned_commit"])
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert subprocess.run(
        ["git", "merge-base", "--is-ancestor", sources[0]["pinned_commit"], head],
        cwd=ROOT, check=False,
    ).returncode == 0

    for directory in (
        "skills/metadata-provenance",
        ".claude/skills/metadata-provenance",
        ".grok/skills/metadata-provenance",
        ".agents/skills/metadata-provenance",
    ):
        path = ROOT / directory / "SKILL.md"
        assert path.is_file(), directory
        assert path.read_bytes() == (ROOT / "skills/metadata-provenance/SKILL.md").read_bytes(), directory

    sync_script = (ROOT / "scripts/agent_capability_sync.py").read_text(encoding="utf-8")
    assert '"metadata-"' in sync_script
    lock = (ROOT / "config/LIVE_LOCK.yaml").read_text(encoding="utf-8")
    assert "live_trading_enabled: false" in lock
    assert "FINAL_EXECUTION_AUTHORIZATION: false" in lock
    assert "LIVE_EXECUTION: BLOCKED" in lock

    print("METADATA_PROVENANCE_FEDERATION=PASS")
    print(f"REQUESTED_REPOSITORIES={len(EXPECTED)}")
    print(f"AGENT_ASSIGNMENTS={len(AGENTS)}")
    print("CANONICAL_AND_PROVIDER_SKILL_ROOTS=PASS")
    print("RUNTIME_DEPENDENCIES=NONE")
    print("CAPITAL_AUTHORITY=FALSE")
    print("LIVE_EXECUTION=BLOCKED")


if __name__ == "__main__":
    main()
