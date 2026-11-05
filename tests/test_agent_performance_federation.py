from pathlib import Path

import pytest

from runtime.agent_federation import PersistentAgentFederation


@pytest.mark.asyncio
async def test_worker_submitted_artifact_is_recorded_without_self_awarded_quality(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    evidence_root.mkdir()
    evidence = evidence_root / "evidence.json"
    evidence.write_text('{"verified": true}', encoding="utf-8")
    federation = PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=tmp_path / "tasks.json",
        performance_path=tmp_path / "scores.json",
        config_hash="cfg",
        source_hash="src",
        lease_seconds=5,
    )
    federation.performance_evaluator.evidence_root = evidence_root
    task = await federation.enqueue_task(
        task_type="TEST_RESEARCH",
        payload={"scope": "test"},
        correlation_id="corr-1",
        assigned_agent="KimiK3",
    )
    claimed = await federation.claim_task("KimiK3", worker_id="kimi-worker-test")
    assert claimed is not None
    assert await federation.complete_task(
        task.task_id,
        agent="KimiK3",
        status="COMPLETED",
        evidence_ref="evidence.json",
        worker_id=claimed.worker_id,
        claim_token=claimed.claim_token,
        result={
            "verified": True,
            "regression_free": True,
            "reproducible": True,
            "efficient": True,
            "handoff_clean": True,
        },
    )
    rows = __import__("json").loads((tmp_path / "scores.json").read_text())["evaluations"]
    assert len(rows) == 1
    assert rows[0]["agent"] == "KimiK3"
    assert rows[0]["total_points"] == 0.0
    assert rows[0]["verification_state"] == "SUBMISSION_ONLY_NOT_QUALIFIED"


@pytest.mark.asyncio
async def test_completed_task_without_evidence_cannot_earn_positive_points(tmp_path: Path) -> None:
    federation = PersistentAgentFederation(
        journal_path=tmp_path / "journal.ndjson",
        lease_path=tmp_path / "leases.json",
        task_path=tmp_path / "tasks.json",
        performance_path=tmp_path / "scores.json",
        config_hash="cfg",
        source_hash="src",
        lease_seconds=5,
    )
    task = await federation.enqueue_task(
        task_type="TEST_RESEARCH",
        payload={},
        correlation_id="corr-2",
        assigned_agent="ClaudeCode",
    )
    claimed = await federation.claim_task(
        "ClaudeCode",
        worker_id="claude-worker-test",
    )
    assert claimed is not None
    with pytest.raises(
        ValueError,
        match="COMPLETED_TASK_REQUIRES_VERIFIABLE_EVIDENCE",
    ):
        await federation.complete_task(
            task.task_id,
            agent="ClaudeCode",
            status="COMPLETED",
            evidence_ref="missing.json",
            result={"verified": True},
            worker_id=claimed.worker_id,
            claim_token=claimed.claim_token,
        )
    assert not (tmp_path / "scores.json").exists()
