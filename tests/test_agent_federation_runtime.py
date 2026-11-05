import asyncio
import tempfile
import unittest
from pathlib import Path

from runtime.agent_federation import PersistentAgentFederation


class AgentFederationTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistent_lease_and_message_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                config_hash="cfg",
                source_hash="src",
                lease_seconds=30,
            )
            await federation.register_agents(["ClaudeCode", "KimiK3", "GrokBot"])
            self.assertEqual(federation.active_agents(), ())
            for agent in ("ClaudeCode", "KimiK3", "GrokBot"):
                await federation.heartbeat(
                    agent,
                    worker_id=f"{agent}-test-worker",
                    origin="TEST",
                )
            await federation.publish(
                sender="ClaudeCode",
                recipients=["AURELIA"],
                message_type="OBSERVATION",
                payload={"finding": "test"},
                correlation_id="c1",
                requires_response=True,
            )
            messages = federation.messages_for("AURELIA")
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]["message_type"], "OBSERVATION")
            self.assertIn("ClaudeCode", federation.active_agents())
            lease = federation._load_leases()["ClaudeCode"]
            self.assertEqual(lease["worker_id"], "ClaudeCode-test-worker")
            self.assertEqual(lease["origin"], "TEST")

    async def test_roundtable_is_durable_and_broadcast(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                config_hash="cfg",
                source_hash="src",
            )
            await federation.register_agents(["ClaudeCode", "KimiK3"])
            await federation.broadcast_roundtable()
            rows = federation.messages_for("ClaudeCode")
            self.assertTrue(any(x["message_type"] == "ROUND_TABLE" for x in rows))


    async def test_task_queue_is_durable_priority_ordered_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            kwargs = dict(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                task_path=f"{td}/tasks.json",
                config_hash="cfg",
                source_hash="src",
            )
            federation = PersistentAgentFederation(**kwargs)
            evidence_root = federation.lease_path.parent / "evidence"
            evidence_root.mkdir(parents=True)
            federation.performance_evaluator.evidence_root = evidence_root
            (evidence_root / "fixture.json").write_text("evidence", encoding="utf-8")
            first = await federation.enqueue_task(
                task_type="RESEARCH",
                payload={"x": 1},
                correlation_id="task-1",
                priority=40,
                assigned_agent="KimiK3",
            )
            duplicate = await federation.enqueue_task(
                task_type="RESEARCH",
                payload={"x": 1},
                correlation_id="task-1",
                priority=40,
                assigned_agent="KimiK3",
            )
            high = await federation.enqueue_task(
                task_type="SECURITY",
                payload={"x": 2},
                correlation_id="task-2",
                priority=90,
                assigned_agent=None,
            )
            self.assertEqual(first.task_id, duplicate.task_id)
            self.assertEqual(federation.pending_tasks()[0]["task_id"], high.task_id)
            claimed = await federation.claim_task("GoogleAgentSkills")
            self.assertIsNotNone(claimed)
            self.assertEqual(claimed.task_id, high.task_id)
            self.assertTrue(await federation.complete_task(high.task_id, agent="GoogleAgentSkills", evidence_ref="fixture.json"))
            self.assertEqual(len(federation.pending_tasks()), 1)

            restored = PersistentAgentFederation(**kwargs)
            self.assertEqual(len(restored.pending_tasks()), 1)
            self.assertEqual(restored.pending_tasks()[0]["task_id"], first.task_id)

    async def test_logical_duplicate_message_is_suppressed(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                config_hash="cfg",
                source_hash="src",
            )
            first = await federation.publish(
                sender="ClaudeCode", recipients=["AURELIA"],
                message_type="OBSERVATION", payload={"finding": "same"},
                correlation_id="dedupe-1",
            )
            second = await federation.publish(
                sender="ClaudeCode", recipients=["AURELIA"],
                message_type="OBSERVATION", payload={"finding": "same"},
                correlation_id="dedupe-1",
            )
            self.assertEqual(first.message_id, second.message_id)
            self.assertEqual(len(federation.messages_for("AURELIA")), 1)

    async def test_external_agent_cannot_claim_capital_authority(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                config_hash="cfg",
                source_hash="src",
            )
            with self.assertRaises(PermissionError):
                await federation.publish(
                    sender="ClaudeCode", recipients=["AURELIA"],
                    message_type="DECISION_PROPOSAL",
                    payload={"capital_authority": True},
                    correlation_id="authority-1",
                )

    async def test_claimed_task_is_requeued_after_lease_expiry(self):
        with tempfile.TemporaryDirectory() as td:
            kwargs = dict(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                task_path=f"{td}/tasks.json",
                config_hash="cfg",
                source_hash="src",
                lease_seconds=5,
            )
            federation = PersistentAgentFederation(**kwargs)
            task = await federation.enqueue_task(
                task_type="RESEARCH",
                payload={"x": 1},
                correlation_id="recover-1",
                assigned_agent="ClaudeCode",
            )
            claimed = await federation.claim_task("ClaudeCode")
            self.assertEqual(claimed.task_id, task.task_id)
            tasks = federation._load_tasks()
            tasks[0]["claimed_at"] = "2000-01-01T00:00:00+00:00"
            federation._save_tasks(tasks)

            recovered = await federation.recover_stale_tasks()
            self.assertEqual(recovered, (task.task_id,))
            self.assertEqual(federation.pending_tasks()[0]["task_id"], task.task_id)

    async def test_stale_agent_is_detectable_after_lease_expiry(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                config_hash="cfg",
                source_hash="src",
                lease_seconds=5,
            )
            await federation.heartbeat(
                "ClaudeCode",
                worker_id="ClaudeCode-test-worker",
                origin="TEST",
            )
            data = federation._load_leases()
            data["ClaudeCode"]["expires_at"] = "2000-01-01T00:00:00+00:00"
            federation._save_leases(data)
            self.assertIn("ClaudeCode", federation.stale_agents())
            self.assertNotIn("ClaudeCode", federation.active_agents())


    async def test_supervisor_origin_is_forbidden(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                config_hash="cfg",
                source_hash="src",
            )
            with self.assertRaises(PermissionError):
                await federation.heartbeat(
                    "ClaudeCode",
                    worker_id="fake-supervisor-worker",
                    origin="SUPERVISOR",
                )
            self.assertEqual(federation.active_agents(), ())

    async def test_worker_id_is_required_for_liveness(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                config_hash="cfg",
                source_hash="src",
            )
            with self.assertRaises(ValueError):
                await federation.heartbeat("ClaudeCode")
            self.assertEqual(federation.active_agents(), ())


    async def test_legacy_lease_never_counts_as_active(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                config_hash="cfg",
                source_hash="src",
                lease_seconds=30,
            )
            federation._save_leases({
                "ClaudeCode": {
                    "lease_id": "legacy",
                    "heartbeat_at": "2099-01-01T00:00:00+00:00",
                    "expires_at": "2099-01-01T00:01:00+00:00",
                }
            })
            self.assertEqual(federation.active_agents(), ())


    async def test_task_completion_requires_matching_worker_claim_capability(self):
        with tempfile.TemporaryDirectory() as td:
            evidence_root = Path(td) / "evidence"
            evidence_root.mkdir()
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                task_path=f"{td}/tasks.json",
                config_hash="cfg",
                source_hash="src",
                lease_seconds=5,
            )
            federation.performance_evaluator.evidence_root = evidence_root
            task = await federation.enqueue_task(
                task_type="ENGINEERING_REVIEW",
                payload={"scope": "claim binding"},
                correlation_id="claim-capability-binding",
                assigned_agent="ClaudeCode",
            )
            claim = await federation.claim_task(
                "ClaudeCode",
                worker_id="worker-one",
            )
            self.assertIsNotNone(claim)
            self.assertTrue(claim.claim_token)

            stored = next(
                row for row in federation._load_tasks()
                if row["task_id"] == task.task_id
            )
            self.assertNotIn(claim.claim_token, str(stored))
            self.assertNotIn(
                claim.claim_token,
                (Path(td) / "events.ndjson").read_text(encoding="utf-8"),
            )

            artifact = evidence_root / "claim-evidence.json"
            artifact.write_text('{"claim":"bound"}', encoding="utf-8")
            self.assertFalse(
                await federation.renew_task_claim(
                    task.task_id,
                    agent="ClaudeCode",
                    worker_id="worker-two",
                    claim_token=claim.claim_token,
                )
            )
            self.assertFalse(
                await federation.complete_task(
                    task.task_id,
                    agent="ClaudeCode",
                    worker_id="worker-two",
                    claim_token=claim.claim_token,
                    evidence_ref="claim-evidence.json",
                )
            )
            self.assertFalse(
                await federation.complete_task(
                    task.task_id,
                    agent="ClaudeCode",
                    worker_id="worker-one",
                    claim_token="wrong-capability",
                    evidence_ref="claim-evidence.json",
                )
            )
            self.assertEqual(
                next(row for row in federation._load_tasks()
                     if row["task_id"] == task.task_id)["status"],
                "CLAIMED",
            )
            self.assertTrue(
                await federation.complete_task(
                    task.task_id,
                    agent="ClaudeCode",
                    worker_id="worker-one",
                    claim_token=claim.claim_token,
                    evidence_ref="claim-evidence.json",
                )
            )
            completed = next(
                row for row in federation._load_tasks()
                if row["task_id"] == task.task_id
            )
            self.assertEqual(completed["status"], "COMPLETED")
            self.assertEqual(completed["completed_by_worker_id"], "worker-one")
            self.assertNotIn("claim_token_sha256", completed)


if __name__ == "__main__":
    unittest.main()
