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
    boundary = load_json("config/agent_capability_boundary.json")
    sot = load_json("AURELIA_SOURCE_OF_TRUTH.json")
    lock_text = (ROOT / "config/LIVE_LOCK.yaml").read_text(encoding="utf-8")

    assert federation["schema"] == "aurelia.agent_skill_federation.v1"
    assert federation["default_policy"]["capital_authority"] is False
    assert federation["default_policy"]["live_order_authority"] is False
    assert federation["default_policy"]["secret_reading"] == "DENY"

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
