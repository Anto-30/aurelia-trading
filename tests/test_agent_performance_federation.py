from pathlib import Path

import pytest

from runtime.agent_federation import PersistentAgentFederation


@pytest.mark.asyncio
async def test_completed_task_creates_evidence_backed_score(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.json"
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
    task = await federation.enqueue_task(
        task_type="TEST_RESEARCH",
        payload={"scope": "test"},
        correlation_id="corr-1",
        assigned_agent="KimiK3",
    )
    claimed = await federation.claim_task("KimiK3")
    assert claimed is not None
    assert await federation.complete_task(
        task.task_id,
        agent="KimiK3",
        status="COMPLETED",
        evidence_ref=str(evidence),
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
    assert rows[0]["total_points"] == 100.0


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
    assert await federation.claim_task("ClaudeCode")
    assert await federation.complete_task(
        task.task_id,
        agent="ClaudeCode",
        status="COMPLETED",
        evidence_ref="missing.json",
        result={"verified": True},
    )
    rows = __import__("json").loads((tmp_path / "scores.json").read_text())["evaluations"]
    assert rows[0]["total_points"] == -25.0
