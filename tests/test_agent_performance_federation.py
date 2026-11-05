from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime.agent_federation import PersistentAgentFederation


class AgentPerformanceFederationTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_submission_is_recorded_without_self_awarded_quality(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence_root = root / "evidence"
            evidence_root.mkdir()
            (evidence_root / "evidence.json").write_text(
                '{"verified": true}',
                encoding="utf-8",
            )
            federation = PersistentAgentFederation(
                journal_path=root / "journal.ndjson",
                lease_path=root / "leases.json",
                task_path=root / "tasks.json",
                performance_path=root / "scores.json",
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
            claim = await federation.claim_task(
                "KimiK3",
                worker_id="kimi-worker-test",
            )
            self.assertIsNotNone(claim)
            self.assertTrue(
                await federation.complete_task(
                    task.task_id,
                    agent="KimiK3",
                    status="COMPLETED",
                    evidence_ref="evidence.json",
                    result={
                        "verified": True,
                        "regression_free": True,
                        "reproducible": True,
                        "efficient": True,
                        "handoff_clean": True,
                    },
                    worker_id=claim.worker_id,
                    claim_token=claim.claim_token,
                )
            )

            rows = json.loads((root / "scores.json").read_text(encoding="utf-8"))["evaluations"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["agent"], "KimiK3")
            self.assertEqual(rows[0]["total_points"], 0.0)
            self.assertEqual(
                rows[0]["verification_state"],
                "SUBMISSION_ONLY_NOT_QUALIFIED",
            )

    async def test_completion_without_verifiable_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence_root = root / "evidence"
            evidence_root.mkdir()
            federation = PersistentAgentFederation(
                journal_path=root / "journal.ndjson",
                lease_path=root / "leases.json",
                task_path=root / "tasks.json",
                performance_path=root / "scores.json",
                config_hash="cfg",
                source_hash="src",
                lease_seconds=5,
            )
            federation.performance_evaluator.evidence_root = evidence_root
            task = await federation.enqueue_task(
                task_type="TEST_RESEARCH",
                payload={},
                correlation_id="corr-2",
                assigned_agent="ClaudeCode",
            )
            claim = await federation.claim_task(
                "ClaudeCode",
                worker_id="claude-worker-test",
            )
            self.assertIsNotNone(claim)

            with self.assertRaisesRegex(
                ValueError,
                "COMPLETED_TASK_REQUIRES_VERIFIABLE_EVIDENCE",
            ):
                await federation.complete_task(
                    task.task_id,
                    agent="ClaudeCode",
                    status="COMPLETED",
                    evidence_ref="missing.json",
                    result={"verified": True},
                    worker_id=claim.worker_id,
                    claim_token=claim.claim_token,
                )

            self.assertFalse((root / "scores.json").exists())
            stored = next(
                row for row in federation._load_tasks()
                if row["task_id"] == task.task_id
            )
            self.assertEqual(stored["status"], "CLAIMED")


if __name__ == "__main__":
    unittest.main()
