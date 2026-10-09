from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    with (ROOT / path).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise AssertionError(f"{path}: expected object")
    return value


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def is_ancestor(commit: str, head: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, head],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
    )


def main() -> None:
    federation = load_json("config/agent_skill_federation.json")
    external_repos = load_json("config/external_repo_federation.json")
    routing = load_json("config/repo_agent_routing.json")
    boundary = load_json("config/agent_capability_boundary.json")
    sot = load_json("AURELIA_SOURCE_OF_TRUTH.json")
    lock_text = (ROOT / "config/LIVE_LOCK.yaml").read_text(encoding="utf-8")

    assert federation["schema"] == "aurelia.agent_skill_federation.v1"
    assert federation["default_policy"]["capital_authority"] is False
    assert federation["default_policy"]["live_order_authority"] is False
    assert federation["default_policy"]["secret_reading"] == "DENY"

    # Every user-requested external source must be pinned and assigned, while
    # remaining outside capital/execution authority.
    assert external_repos["schema"] == "aurelia.external_repo_federation.v1"
    controls = external_repos["global_controls"]
    assert controls["capital_authority"] is False
    assert controls["live_order_submission"] is False
    assert controls["live_lock_mutation"] is False
    assert controls["secret_reading"] is False
    assert controls["broker_transaction_write"] is False
    known_agents = set(routing["agents"])
    expected_external = {
        "CryptoSignal/Crypto-Signal": "7cb9c5c6cd226c6fe2d345e4bda3bec8156cefec",
        "BerriAI/litellm": "5e1c5c0bd17781a83b4368c38ebebcf7bc683fcb",
        "LiteLLM-Labs/litellm-agent-control-plane": "53bfd20e2fec51fc8f665fb614512c6b138367da",
        "BerriAI/litellm-docs": "4a73adff0a530b948b043b0fa64bf96d2cc7c4ce",
        "BerriAI/liteLLM-proxy": "1ef69ae92bf22600f9a42d15e3b992e1010c9a7e",
        "numman-ali/cc-mirror": "e0e6f289c78ebe7f38bd8afcad92d28ea7e4f1e5",
        "BerriAI/litellm-pgvector": "5bd8f3ab1fa9129e758a2c4b17ba1c6f3047ba24",
        "LiteLLM-Labs/litellm-rust": "76f83257fce4dcc3d76e7e760934bbd725b624d9",
        "langchain-ai/langchain-litellm": "5b8af479f783ae5a0d3eff9214c2cbb06473e513",
        "Kappaemme-git/codex-first-customer-finder-skill": "d3f6964bd989745ac183edbd545c588a68451146",
        "Neeeophytee/finding-unknowns-skills": "ca5696a0f08d2de6b2997fff1d6cc05c3ed587cc",
        "he-yufeng/FindJobs-Agent": "591fe6b451db98fe0bebb8f92a7b9902b0fd6079",
        "davepoon/buildwithclaude": "616deb5c66db0b06a6afeb7ae675e70a1b6e3b34",
        "workersio/skills": "0e3950fc7b284db4f6b317e48bcb99edd2c1e3bb",
    }
    expected_primary = {
        "BerriAI/litellm": "GoogleAgentSkills",
        "LiteLLM-Labs/litellm-agent-control-plane": "GrokBot",
        "BerriAI/litellm-docs": "GLM",
        "BerriAI/liteLLM-proxy": "ClaudeCode",
        "numman-ali/cc-mirror": "ClaudeCode",
        "BerriAI/litellm-pgvector": "ClaudeCode",
        "LiteLLM-Labs/litellm-rust": "ClaudeCode",
        "langchain-ai/langchain-litellm": "ClaudeCode",
    }
    all_external = external_repos["repositories"]
    assert len({item["repo"] for item in all_external}) == len(all_external)
    assert all(item.get("head_commit") and item["head_commit"] != "SYNC_REQUIRED" for item in all_external)
    registered = {item["repo"]: item for item in all_external}
    for repo, expected_commit in expected_external.items():
        item = registered[repo]
        assert item["head_commit"] == expected_commit, repo
        assert item["assigned_agents"], repo
        assert set(item["assigned_agents"]).issubset(known_agents), repo
        assert item["mode"] in {"RESEARCH_ONLY", "SANDBOX_ONLY", "TOOLCHAIN_ONLY", "REFERENCE_ONLY"}, repo

    registered_skills = {item["repo"]: item for item in federation["sources"]}
    for repo, expected_commit in expected_external.items():
        item = registered_skills[repo]
        assert item["pinned_commit"] == expected_commit, repo
        assert item["capital_authority"] is False, repo
        assert set(item.get("assigned_agents", [])).issubset(known_agents), repo

    for repo, expected_agent in expected_primary.items():
        repo_item = registered[repo]
        skill_item = registered_skills[repo]
        assert repo_item["assigned_agents"][0] == expected_agent, (
            repo, "repo primary routing mismatch", repo_item["assigned_agents"]
        )
        assert skill_item["assigned_agents"][0] == expected_agent, (
            repo, "skill primary routing mismatch", skill_item["assigned_agents"]
        )

    sources = federation.get("sources", [])
    assert len(sources) >= 7
    for source in sources:
        assert source["pinned_commit"], source["name"]
        assert source["capital_authority"] is False, source["name"]

    assert boundary["capital_authority"] is False
    for actor_name, actor in boundary["actors"].items():
        assert actor["capital_authority"] is False if actor_name != "AURELIA" else True

    assert "live_trading_enabled: false" in lock_text
    assert "FINAL_EXECUTION_AUTHORIZATION: false" in lock_text
    assert "LIVE_EXECUTION: BLOCKED" in lock_text

    evidence = load_json(
        "reports/certification/SIMULATION_VERIFIED_NONPROD_3600S_2026-10-04.json"
    )
    assert evidence["evidence_class"] == "SIMULATION_VERIFIED"
    assert evidence["duration_seconds"] >= evidence["target_seconds"] >= 3600
    assert evidence["health_check_failures"] == 0
    assert evidence["authenticated_deriv_session"] is False
    assert evidence["real_broker_transaction"] is False
    assert evidence["real_capital_movement"] is False
    assert evidence["final_execution_authorization"] is False
    assert evidence["live_execution"] == "BLOCKED"

    head = git_head()
    assert is_ancestor(evidence["source_commit"], head), (
        evidence["source_commit"],
        head,
    )
    assert sot["live_lock_active"] is True
    assert sot["final_execution_authorization_current"] is False
    assert sot["live_execution_current"] == "BLOCKED"

    print("AGENT_FEDERATION_AUDIT=PASS")
    print(f"CURRENT_HEAD={head}")
    print(f"SOAK_EVIDENCE_SOURCE={evidence['source_commit']}")
    print("CAPITAL_AUTHORITY=FALSE")
    print("LIVE_EXECUTION=BLOCKED")


if __name__ == "__main__":
    main()
