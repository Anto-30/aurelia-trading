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
    capability_matrix = load_json("config/agent_capability_matrix.json")
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
        "jxjhheric/freebuff2api-wokers": "5cbb353019f2f660ca1d72984549e430590b4778",
        "kele68108/Freebuff2API-Optimized": "f7e13d414e9a7197a227969d88ad6166724c2a15",
        "t479842598/freebuff2api-vercel": "16274ad8f3b9fa9c30093ab859f3732aca043452",
        "HengXin666/freebuff-proxy": "581097b0b7ba14a57fca487936975d97474d9bb8",
        "lza6/Freebuff-2API": "bd607aac70548b80f586c60f819ed8e47240e25f",
        "NetroIndonesia/freebuff2api": "4894d7db6157c97f3037dc7d79ae0c2571762f8e",
        "XxxXTeam/freebuff2api": "0c691c7dc90b91589e53901ea39dee96b28bf157",
        "Quorinex/Freebuff2API": "a1c10357098f0615a8b605bf32ed9455e33320e4",
        "pingmike2/freebuff2api-wokers": "901a9d87c748072fea16c8cc4d5e9d3bca87d593",
        "CodebuffAI/freebuff": "18f32cd3c51ea88d763e89432642a908030fd088",
        "VenTheZone/freebuff-gate": "3663a93614f0abbfcb477563538014e1f35b0cd4",
        "Praket7/freebuff-mcp": "02cf6e623cc6643fba3aeadeba3011188857212d",
        "Jakevin/codex-freebuff-web": "576c6835bc06ed4fc039bb6cd264e73ce36efa41",
        "TheMetalStorm/herdr-freebuff-plugin": "a49b1ea428fe6eb620288a3035984073927557d2",
        "Heartcoolman/FreeBuff": "9edc400ca83c347554dba8fb373e63af8fcfbcd2",
        "HaizhuAI/Freebuff2apic": "58ff9bdbbc749b8a607a2960ee89d6f29927ca0f",
        "0xgetz/freebuff-9router": "ec5e698816d86b4db1d970e03d10350bcc15d966",
        "aminkalantari842-ui/global-intelligence-os": "05ea36d535e2076a359b7fdeb82d99e77f66ae4e",
        "6yte96/freebuffet": "280259f0495f8d37b7cd51a19500e8eb0eab8223",
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
        "pineforge-4pass/pineforge-engine": "873b25daa00687cd2b9b9d6b2e49c57149227edd",
        "pinecone-io/pinecone-claude-code-plugin": "c383d38b5cc3c5ec219f2e68026e47ffbf46524a",
        "tmustier/pine-of-glass": "6e7dd5fd613198fee9fff71df1bc45a579030cce",
        "FaustoS88/Pydantic-AI-Pinescript-Expert": "03cbd93c486435df08d70185fbab9aa61fff5fbb",
        "be-thomas/OpenPineScript": "a793e719043a0a05dc7c184b04ef4ad6985d0de9",
        "jpantsjoha/pinescript-vscode-extension": "b81aa3d88f6327328ebf84b851757bd6266e56f8",
        "double232/pinescript-skill": "107fd4c6f4abd6cf64639040d6d67b42d130aa3d",
        "gugu91/pinet": "78b24b7ce6abd3e7cb793b31a399041c7d6a3c7a",
        "folknor/pine-tools": "3dd9f3c941ece3368e500360dd9e6e125ad396f6",
        "dharmanan/PineScript-coder": "5f4c0f65e58b60860a920c2c59670ed21b1a9eaa",
        "dotsystemsdevs/pineflow": "8d2dbbc2a5b3061d102c6beb2e9070c4c4f05e3d",
        "batonogov/pine": "c5ed7a4c4744c4dfd4ff88dd20cc94a2c81b96d1",
        "edeng23/pines": "c6020543236360c92adff8ee48d621b1d4b3759f",
        "TheFractalyst/PineMCP": "c630de784c795d8abc5e15780881f5237dba8bdc",
        "85599/pinesprout": "48bcea15275351869dffa1a3ba5fa6ffebd1f983",
        "hasnocool/tradingview-script-downloader": "997d5417235c4fa9d4e20d56b02fe6b0fd3fd37d",
        "coocolab/Coocolab-Tradingview-MCP": "cd16a7dc038762688e7807a26285a26337d6fc60",
        "daviddme/tradingview-indicator-search-mcp-server": "1f8648936088cf189e4ac1a23b55c522c11d15cd",
        "kashsuks/Pinel": "1b10a5f8c8f772a27360d77dae33be5137bc7a66",
        "pinecone-io/getting-started-with-pinecone-webinar": "76068a1b11a5c33dd82192f31ba5377c46c656cf",
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
        "jxjhheric/freebuff2api-wokers": "GoogleAgentSkills",
        "kele68108/Freebuff2API-Optimized": "GoogleAgentSkills",
        "t479842598/freebuff2api-vercel": "GoogleAgentSkills",
        "HengXin666/freebuff-proxy": "GoogleAgentSkills",
        "lza6/Freebuff-2API": "GoogleAgentSkills",
        "NetroIndonesia/freebuff2api": "GoogleAgentSkills",
        "XxxXTeam/freebuff2api": "GoogleAgentSkills",
        "Quorinex/Freebuff2API": "GoogleAgentSkills",
        "pingmike2/freebuff2api-wokers": "GoogleAgentSkills",
        "CodebuffAI/freebuff": "ClaudeCode",
        "VenTheZone/freebuff-gate": "PlaywrightCLI",
        "Praket7/freebuff-mcp": "GoogleAgentSkills",
        "Jakevin/codex-freebuff-web": "ClaudeCode",
        "TheMetalStorm/herdr-freebuff-plugin": "GrokBot",
        "Heartcoolman/FreeBuff": "GoogleAgentSkills",
        "HaizhuAI/Freebuff2apic": "GoogleAgentSkills",
        "0xgetz/freebuff-9router": "GoogleAgentSkills",
        "aminkalantari842-ui/global-intelligence-os": "GrokBot",
        "6yte96/freebuffet": "ClaudeCode",
        "pineforge-4pass/pineforge-engine": "KimiK3",
        "pinecone-io/pinecone-claude-code-plugin": "ClaudeCode",
        "tmustier/pine-of-glass": "ClaudeCode",
        "FaustoS88/Pydantic-AI-Pinescript-Expert": "KimiK3",
        "be-thomas/OpenPineScript": "KimiK3",
        "jpantsjoha/pinescript-vscode-extension": "ClaudeCode",
        "double232/pinescript-skill": "ClaudeCode",
        "gugu91/pinet": "ClaudeCode",
        "folknor/pine-tools": "ClaudeCode",
        "dharmanan/PineScript-coder": "KimiK3",
        "dotsystemsdevs/pineflow": "ClaudeCode",
        "batonogov/pine": "ClaudeCode",
        "edeng23/pines": "ClaudeCode",
        "TheFractalyst/PineMCP": "GoogleAgentSkills",
        "85599/pinesprout": "KimiK3",
        "hasnocool/tradingview-script-downloader": "ClaudeCode",
        "coocolab/Coocolab-Tradingview-MCP": "GoogleAgentSkills",
        "daviddme/tradingview-indicator-search-mcp-server": "GoogleAgentSkills",
        "kashsuks/Pinel": "ClaudeCode",
        "pinecone-io/getting-started-with-pinecone-webinar": "ClaudeCode",
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
    assert len({item["name"] for item in federation["sources"]}) == len(federation["sources"]), "duplicate external skill names"
    for repo, expected_commit in expected_external.items():
        item = registered_skills[repo]
        assert item["pinned_commit"] == expected_commit, repo
        assert item["capital_authority"] is False, repo
        assert set(item.get("assigned_agents", [])).issubset(known_agents), repo

    matrix_assignments = capability_matrix.get("external_source_assignments", {})
    matrix_federation = capability_matrix.get("federated_repositories", {})
    for repo, expected_agent in expected_primary.items():
        repo_item = registered[repo]
        skill_item = registered_skills[repo]
        matrix_item = matrix_assignments[repo]
        assert repo_item["assigned_agents"][0] == expected_agent, (
            repo, "repo primary routing mismatch", repo_item["assigned_agents"]
        )
        assert skill_item["assigned_agents"][0] == expected_agent, (
            repo, "skill primary routing mismatch", skill_item["assigned_agents"]
        )
        assert matrix_item["primary"] == expected_agent, (
            repo, "capability-matrix primary routing mismatch", matrix_item.get("primary")
        )
        assert matrix_item["mode"] == repo_item["mode"], (
            repo, "capability-matrix mode mismatch", matrix_item.get("mode"), repo_item["mode"]
        )
        assert set(matrix_item.get("supporting", [])).issubset(
            set(repo_item["assigned_agents"])
        ), (repo, "capability-matrix has unknown supporting agents")
        assert matrix_federation[repo] == repo_item["assigned_agents"], (
            repo, "capability-matrix assigned agents mismatch"
        )
        assert repo_item.get("capital_authority", False) is False
        assert skill_item.get("capital_authority", False) is False

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
