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
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(path)
    return value

def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()

def main() -> None:
    lock = (ROOT / "config/LIVE_LOCK.yaml").read_text(encoding="utf-8")
    federation = load_json("config/agent_skill_federation.json")
    boundary = load_json("config/agent_capability_boundary.json")
    matrix = load_json("config/agent_capability_matrix.json")
    continuity = load_json("config/agent_continuity_policy.json")
    evidence = load_json("reports/certification/SIMULATION_VERIFIED_NONPROD_3600S_2026-10-04.json")
    require(
        "live_trading_enabled: false" in lock,
        location="scripts/agent_continuity_check.py:25",
    )
    require(
        "FINAL_EXECUTION_AUTHORIZATION: false" in lock,
        location="scripts/agent_continuity_check.py:26",
    )
    require(
        "LIVE_EXECUTION: BLOCKED" in lock,
        location="scripts/agent_continuity_check.py:27",
    )
    require(
        federation["default_policy"]["capital_authority"] is False,
        location="scripts/agent_continuity_check.py:28",
    )
    require(
        federation["default_policy"]["live_order_authority"] is False,
        location="scripts/agent_continuity_check.py:29",
    )
    require(
        federation["default_policy"]["secret_reading"] == "DENY",
        location="scripts/agent_continuity_check.py:30",
    )
    require(
        boundary["capital_authority"] is False,
        location="scripts/agent_continuity_check.py:31",
    )
    for name, actor in boundary["actors"].items():
        require(
            actor["capital_authority"] is (name == "AURELIA"),
            name,
            location="scripts/agent_continuity_check.py:33",
        )
    require(
        matrix["forbidden_for_external_agents"],
        location="scripts/agent_continuity_check.py:34",
    )
    require(
        matrix["connection_truth"],
        location="scripts/agent_continuity_check.py:35",
    )
    for source in federation["sources"]:
        sha = source["pinned_commit"]
        if source.get("pin_status") == "UPSTREAM_IDENTIFIER_FORMAT_ANOMALY":
            require(
                source.get("pin_validation_note"),
                source["name"],
                location="scripts/agent_continuity_check.py:39",
            )
            continue
        require(
            len(sha) == 40 and sha == sha.lower(),
            source["name"],
            location="scripts/agent_continuity_check.py:41",
        )
    require(
        continuity["capital_authority"] is False,
        location="scripts/agent_continuity_check.py:42",
    )
    require(
        continuity["heartbeat_seconds"] > 0,
        location="scripts/agent_continuity_check.py:43",
    )
    require(
        evidence["evidence_class"] == "SIMULATION_VERIFIED",
        location="scripts/agent_continuity_check.py:44",
    )
    require(
        evidence["duration_seconds"] >= 3600,
        location="scripts/agent_continuity_check.py:45",
    )
    require(
        evidence["health_check_failures"] == 0,
        location="scripts/agent_continuity_check.py:46",
    )
    require(
        evidence["final_execution_authorization"] is False,
        location="scripts/agent_continuity_check.py:47",
    )
    require(
        evidence["live_execution"] == "BLOCKED",
        location="scripts/agent_continuity_check.py:48",
    )
    print("AGENT_CONTINUITY_CHECK=PASS")
    print(f"LOCAL_HEAD={git_head()}")
    print("CAPITAL_AUTHORITY=FALSE")
    print("LIVE_EXECUTION=BLOCKED")

if __name__ == "__main__":
    main()