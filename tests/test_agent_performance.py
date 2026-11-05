from pathlib import Path

import pytest

from runtime.agent_performance import AgentPerformanceLedger


def test_evidence_backed_award_and_leaderboard(tmp_path: Path) -> None:
    ledger = AgentPerformanceLedger(tmp_path / "scores.json")
    result = ledger.award(
        agent="KimiK3", task_id="task:1",
        category_scores={"correctness": 25, "evidence_quality": 20, "task_outcome": 20,
                         "robustness": 15, "reproducibility": 10, "efficiency": 5, "collaboration": 5},
        evidence_ref="artifacts/eval-1.json", evaluation_id="eval-1", timestamp=1000)
    assert result.total_points == 100
    assert ledger.leaderboard(now=1000)[0]["agent"] == "KimiK3"


def test_agents_cannot_self_award(tmp_path: Path) -> None:
    ledger = AgentPerformanceLedger(tmp_path / "scores.json")
    with pytest.raises(PermissionError):
        ledger.award(agent="KimiK3", task_id="task:1", category_scores={"correctness": 10},
                     evidence_ref="artifacts/eval-1.json", evaluation_id="eval-1", evaluator="KimiK3")


def test_penalty_and_decay(tmp_path: Path) -> None:
    ledger = AgentPerformanceLedger(tmp_path / "scores.json", decay_days=90)
    ledger.award(agent="ClaudeCode", task_id="task:1", category_scores={"correctness": 20, "task_outcome": 20},
                 evidence_ref="artifacts/eval-1.json", evaluation_id="eval-1", timestamp=0)
    ledger.award(agent="ClaudeCode", task_id="task:2", category_scores={}, penalty=-50,
                 evidence_ref="artifacts/eval-2.json", evaluation_id="eval-2", timestamp=90 * 86400)
    assert ledger.leaderboard(now=90 * 86400)[0]["decayed_net_points"] == -30


def test_worker_self_attested_quality_flags_do_not_award_points(tmp_path: Path) -> None:
    from runtime.agent_performance import AgentPerformanceEvaluator

    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    artifact = evidence_root / "worker-output.json"
    artifact.write_text('{"submitted": true}', encoding="utf-8")
    ledger = AgentPerformanceLedger(tmp_path / "scores.json")
    evaluator = AgentPerformanceEvaluator(ledger, evidence_root=evidence_root)

    result = evaluator.evaluate(
        agent="ClaudeCode",
        task_id="task:self-asserted",
        status="COMPLETED",
        evidence_ref="worker-output.json",
        result={
            "verified": True,
            "regression_free": True,
            "reproducible": True,
            "efficient": True,
            "handoff_clean": True,
        },
    )

    assert result["total_points"] == 0.0
    assert result["verification_state"] == "SUBMISSION_ONLY_NOT_QUALIFIED"
    assert all(value == 0.0 for value in result["category_scores"].values())
