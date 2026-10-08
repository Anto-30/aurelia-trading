from pathlib import Path

from runtime.agent_performance import AgentPerformanceLedger


def test_leaderboard_exposes_rank_success_penalties_and_exact_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
    evidence.write_bytes(b'{"verified":true}')
    ledger = AgentPerformanceLedger(tmp_path / "scores.json")
    ledger.award(
        agent="KimiK3",
        task_id="task:leaderboard",
        category_scores={
            "correctness": 25, "evidence_quality": 20, "task_outcome": 20,
            "robustness": 15, "reproducibility": 10, "efficiency": 5, "collaboration": 5,
        },
        evidence_ref=str(evidence),
        evaluation_id="eval:leaderboard",
        timestamp=1000,
    )
    snapshot = ledger.snapshot(now=1000)
    row = snapshot["agents"][0]
    assert row["rank"] == 1
    assert row["gross_points"] == 100.0
    assert row["decayed_net_points"] == 100.0
    assert row["successful_task_rate"] == 1.0
    assert row["evidence_quality_rate"] == 1.0
    assert row["penalty_points"] == 0.0
    evidence_row = snapshot["evidence"][0]
    assert evidence_row["evaluation_id"] == "eval:leaderboard"
    assert evidence_row["evidence_ref"] == str(evidence)
    assert evidence_row["evidence_sha256"]
    assert evidence_row["evidence_size_bytes"] == evidence.stat().st_size


def test_leadership_requires_ten_evaluations(tmp_path: Path) -> None:
    ledger = AgentPerformanceLedger(tmp_path / "scores.json")
    for i in range(9):
        ledger.award(
            agent="ClaudeCode", task_id=f"task:{i}",
            category_scores={"task_outcome": 20},
            evidence_ref=f"evidence:{i}", evaluation_id=f"eval:{i}", timestamp=i,
        )
    assert ledger.leaderboard(now=1000)[0]["leadership_eligible"] is False
    ledger.award(
        agent="ClaudeCode", task_id="task:9",
        category_scores={"task_outcome": 20},
        evidence_ref="evidence:9", evaluation_id="eval:9", timestamp=9,
    )
    assert ledger.leaderboard(now=1000)[0]["leadership_eligible"] is True
