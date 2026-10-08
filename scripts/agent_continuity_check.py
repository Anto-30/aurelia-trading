from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

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
    assert "live_trading_enabled: false" in lock
    assert "FINAL_EXECUTION_AUTHORIZATION: false" in lock
    assert "LIVE_EXECUTION: BLOCKED" in lock
    assert federation["default_policy"]["capital_authority"] is False
    assert federation["default_policy"]["live_order_authority"] is False
    assert federation["default_policy"]["secret_reading"] == "DENY"
    assert boundary["capital_authority"] is False
    for name, actor in boundary["actors"].items():
        assert actor["capital_authority"] is (name == "AURELIA"), name
    assert matrix["forbidden_for_external_agents"]
    assert matrix["connection_truth"]
    for source in federation["sources"]:
        sha = source["pinned_commit"]
        if source.get("pin_status") == "UPSTREAM_IDENTIFIER_FORMAT_ANOMALY":
            assert source.get("pin_validation_note"), source["name"]
            continue
        assert len(sha) == 40 and sha == sha.lower(), source["name"]
    assert continuity["capital_authority"] is False
    assert continuity["heartbeat_seconds"] > 0
    assert evidence["evidence_class"] == "SIMULATION_VERIFIED"
    assert evidence["duration_seconds"] >= 3600
    assert evidence["health_check_failures"] == 0
    assert evidence["final_execution_authorization"] is False
    assert evidence["live_execution"] == "BLOCKED"
    print("AGENT_CONTINUITY_CHECK=PASS")
    print(f"LOCAL_HEAD={git_head()}")
    print("CAPITAL_AUTHORITY=FALSE")
    print("LIVE_EXECUTION=BLOCKED")

if __name__ == "__main__":
    main()