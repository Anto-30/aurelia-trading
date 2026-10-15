from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]



def require(condition, message=None, *, location=""):
    """Enforce a runtime invariant even when Python optimization is enabled."""
    if not condition:
        detail = message if message is not None else "validation condition failed"
        prefix = f"{location}: " if location else ""
        raise AssertionError(f"{prefix}{detail}")

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

    require(
        federation["schema"] == "aurelia.agent_skill_federation.v1",
        location="scripts/validate_agent_federation.py:45",
    )
    require(
        federation["default_policy"]["capital_authority"] is False,
        location="scripts/validate_agent_federation.py:46",
    )
    require(
        federation["default_policy"]["live_order_authority"] is False,
        location="scripts/validate_agent_federation.py:47",
    )
    require(
        federation["default_policy"]["secret_reading"] == "DENY",
        location="scripts/validate_agent_federation.py:48",
    )

    # Every user-requested external source must be pinned and assigned, while
    # remaining outside capital/execution authority.
    require(
        external_repos["schema"] == "aurelia.external_repo_federation.v1",
        location="scripts/validate_agent_federation.py:52",
    )
    controls = external_repos["global_controls"]
    require(
        controls["capital_authority"] is False,
        location="scripts/validate_agent_federation.py:54",
    )
    require(
        controls["live_order_submission"] is False,
        location="scripts/validate_agent_federation.py:55",
    )
    require(
        controls["live_lock_mutation"] is False,
        location="scripts/validate_agent_federation.py:56",
    )
    require(
        controls["secret_reading"] is False,
        location="scripts/validate_agent_federation.py:57",
    )
    require(
        controls["broker_transaction_write"] is False,
        location="scripts/validate_agent_federation.py:58",
    )
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
    }
    all_external = external_repos["repositories"]
    require(
        len({item["repo"] for item in all_external}) == len(all_external),
        location="scripts/validate_agent_federation.py:125",
    )
    require(
        all(item.get("head_commit") and item["head_commit"] != "SYNC_REQUIRED" for item in all_external),
        location="scripts/validate_agent_federation.py:126",
    )
    registered = {item["repo"]: item for item in all_external}
    for repo, expected_commit in expected_external.items():
        item = registered[repo]
        require(
            item["head_commit"] == expected_commit,
            repo,
            location="scripts/validate_agent_federation.py:130",
        )
        require(
            item["assigned_agents"],
            repo,
            location="scripts/validate_agent_federation.py:131",
        )
        require(
            set(item["assigned_agents"]).issubset(known_agents),
            repo,
            location="scripts/validate_agent_federation.py:132",
        )
        require(
            item["mode"] in {"RESEARCH_ONLY", "SANDBOX_ONLY", "TOOLCHAIN_ONLY", "REFERENCE_ONLY"},
            repo,
            location="scripts/validate_agent_federation.py:133",
        )

    registered_skills = {item["repo"]: item for item in federation["sources"]}
    require(
        len({item["name"] for item in federation["sources"]}) == len(federation["sources"]),
        "duplicate external skill names",
        location="scripts/validate_agent_federation.py:136",
    )
    for repo, expected_commit in expected_external.items():
        item = registered_skills[repo]
        require(
            item["pinned_commit"] == expected_commit,
            repo,
            location="scripts/validate_agent_federation.py:139",
        )
        require(
            item["capital_authority"] is False,
            repo,
            location="scripts/validate_agent_federation.py:140",
        )
        require(
            set(item.get("assigned_agents", [])).issubset(known_agents),
            repo,
            location="scripts/validate_agent_federation.py:141",
        )

    matrix_assignments = capability_matrix.get("external_source_assignments", {})
    matrix_federation = capability_matrix.get("federated_repositories", {})
    for repo, expected_agent in expected_primary.items():
        repo_item = registered[repo]
        skill_item = registered_skills[repo]
        matrix_item = matrix_assignments[repo]
        require(
            repo_item["assigned_agents"][0] == expected_agent,
            (
                        repo, "repo primary routing mismatch", repo_item["assigned_agents"]
                    ),
            location="scripts/validate_agent_federation.py:149",
        )
        require(
            skill_item["assigned_agents"][0] == expected_agent,
            (
                        repo, "skill primary routing mismatch", skill_item["assigned_agents"]
                    ),
            location="scripts/validate_agent_federation.py:152",
        )
        require(
            matrix_item["primary"] == expected_agent,
            (
                        repo, "capability-matrix primary routing mismatch", matrix_item.get("primary")
                    ),
            location="scripts/validate_agent_federation.py:155",
        )
        require(
            matrix_item["mode"] == repo_item["mode"],
            (
                        repo, "capability-matrix mode mismatch", matrix_item.get("mode"), repo_item["mode"]
                    ),
            location="scripts/validate_agent_federation.py:158",
        )
        require(
            set(matrix_item.get("supporting", [])).issubset(
                        set(repo_item["assigned_agents"])
                    ),
            (repo, "capability-matrix has unknown supporting agents"),
            location="scripts/validate_agent_federation.py:161",
        )
        require(
            matrix_federation[repo] == repo_item["assigned_agents"],
            (
                        repo, "capability-matrix assigned agents mismatch"
                    ),
            location="scripts/validate_agent_federation.py:164",
        )
        require(
            repo_item.get("capital_authority", False) is False,
            location="scripts/validate_agent_federation.py:167",
        )
        require(
            skill_item.get("capital_authority", False) is False,
            location="scripts/validate_agent_federation.py:168",
        )

    sources = federation.get("sources", [])
    require(
        len(sources) >= 7,
        location="scripts/validate_agent_federation.py:171",
    )
    for source in sources:
        require(
            source["pinned_commit"],
            source["name"],
            location="scripts/validate_agent_federation.py:173",
        )
        require(
            source["capital_authority"] is False,
            source["name"],
            location="scripts/validate_agent_federation.py:174",
        )

    require(
        boundary["capital_authority"] is False,
        location="scripts/validate_agent_federation.py:176",
    )
    for actor_name, actor in boundary["actors"].items():
        require(
            actor["capital_authority"] is False if actor_name != "AURELIA" else True,
            location="scripts/validate_agent_federation.py:178",
        )

    require(
        "live_trading_enabled: false" in lock_text,
        location="scripts/validate_agent_federation.py:180",
    )
    require(
        "FINAL_EXECUTION_AUTHORIZATION: false" in lock_text,
        location="scripts/validate_agent_federation.py:181",
    )
    require(
        "LIVE_EXECUTION: BLOCKED" in lock_text,
        location="scripts/validate_agent_federation.py:182",
    )

    evidence = load_json(
        "reports/certification/SIMULATION_VERIFIED_NONPROD_3600S_2026-10-04.json"
    )
    require(
        evidence["evidence_class"] == "SIMULATION_VERIFIED",
        location="scripts/validate_agent_federation.py:187",
    )
    require(
        evidence["duration_seconds"] >= evidence["target_seconds"] >= 3600,
        location="scripts/validate_agent_federation.py:188",
    )
    require(
        evidence["health_check_failures"] == 0,
        location="scripts/validate_agent_federation.py:189",
    )
    require(
        evidence["authenticated_deriv_session"] is False,
        location="scripts/validate_agent_federation.py:190",
    )
    require(
        evidence["real_broker_transaction"] is False,
        location="scripts/validate_agent_federation.py:191",
    )
    require(
        evidence["real_capital_movement"] is False,
        location="scripts/validate_agent_federation.py:192",
    )
    require(
        evidence["final_execution_authorization"] is False,
        location="scripts/validate_agent_federation.py:193",
    )
    require(
        evidence["live_execution"] == "BLOCKED",
        location="scripts/validate_agent_federation.py:194",
    )

    head = git_head()
    require(
        is_ancestor(evidence["source_commit"], head),
        (
                evidence["source_commit"],
                head,
            ),
        location="scripts/validate_agent_federation.py:197",
    )
    require(
        sot["live_lock_active"] is True,
        location="scripts/validate_agent_federation.py:201",
    )
    require(
        sot["final_execution_authorization_current"] is False,
        location="scripts/validate_agent_federation.py:202",
    )
    require(
        sot["live_execution_current"] == "BLOCKED",
        location="scripts/validate_agent_federation.py:203",
    )

    print("AGENT_FEDERATION_AUDIT=PASS")
    print(f"CURRENT_HEAD={head}")
    print(f"SOAK_EVIDENCE_SOURCE={evidence['source_commit']}")
    print("CAPITAL_AUTHORITY=FALSE")
    print("LIVE_EXECUTION=BLOCKED")


if __name__ == "__main__":
    main()
