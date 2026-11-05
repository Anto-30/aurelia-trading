import asyncio
import tempfile
import unittest

from runtime.agent_federation import PersistentAgentFederation
from runtime.worker_runtime import SupervisedAgentWorker


class SupervisedWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_unavailable_provider_does_not_create_active_lease(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                task_path=f"{td}/tasks.json",
                config_hash="cfg",
                source_hash="src",
            )
            worker = SupervisedAgentWorker(
                federation, agent="ClaudeCode", handler=None
            )
            status = await worker.start()
            self.assertEqual(status.state, "UNAVAILABLE")
            self.assertNotIn("ClaudeCode", federation.active_agents())

    async def test_worker_owns_lease_and_processes_task(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                task_path=f"{td}/tasks.json",
                config_hash="cfg",
                source_hash="src",
                lease_seconds=3,
            )
            evidence_root = federation.lease_path.parent / "evidence"
            evidence_root.mkdir(parents=True)
            federation.performance_evaluator.evidence_root = evidence_root
            seen = []

            async def handler(task):
                seen.append(task.task_id)
                (evidence_root / "worker-result.json").write_text("evidence", encoding="utf-8")
                return {
                    "accepted": True,
                    "evidence_ref": "worker-result.json",
                    "artifact_type": "application/json",
                    "access_token": "must-not-be-persisted",
                }

            worker = SupervisedAgentWorker(
                federation,
                agent="ClaudeCode",
                handler=handler,
                poll_seconds=0.05,
                worker_id="claude-real-worker-test",
            )
            task = await federation.enqueue_task(
                task_type="ENGINEERING",
                payload={"action": "test"},
                correlation_id="worker-1",
                assigned_agent="ClaudeCode",
            )
            status = await worker.start()
            self.assertEqual(status.state, "ACTIVE")
            self.assertIn("ClaudeCode", federation.active_agents())

            for _ in range(30):
                if task.task_id in seen:
                    break
                await __import__("asyncio").sleep(0.05)

            self.assertEqual(seen, [task.task_id])
            rows = federation._load_tasks()
            self.assertEqual(rows[0]["status"], "COMPLETED")
            self.assertEqual(rows[0]["evidence_ref"], "worker-result.json")
            self.assertEqual(rows[0]["completed_by_worker_id"], "claude-real-worker-test")
            self.assertEqual(rows[0]["result"], {"artifact_type": "application/json"})
            self.assertNotIn("access_token", str(rows[0]))
            acknowledgements = [
                message for message in federation.messages_for("AURELIA")
                if message["message_type"] == "WORKER_ACK"
                and message["payload"]["task_id"] == task.task_id
            ]
            self.assertEqual(len(acknowledgements), 1)
            self.assertEqual(
                acknowledgements[0]["payload"]["result"],
                {"artifact_type": "application/json"},
            )
            self.assertNotIn(
                "must-not-be-persisted",
                (federation.journal.path).read_text(encoding="utf-8"),
            )
            await worker.stop()
            self.assertEqual(worker.status.state, "STOPPED")
            self.assertNotIn("ClaudeCode", federation.active_agents())

    async def test_in_process_worker_renews_long_running_claim(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                task_path=f"{td}/tasks.json",
                config_hash="cfg",
                source_hash="src",
                lease_seconds=5,
            )
            # A short lease makes the renewal regression deterministic.
            federation.lease_seconds = 0.3
            evidence_root = federation.lease_path.parent / "evidence"
            evidence_root.mkdir(parents=True)
            federation.performance_evaluator.evidence_root = evidence_root
            started = asyncio.Event()

            async def handler(task):
                started.set()
                await asyncio.sleep(0.8)
                (evidence_root / "long-result.json").write_text(
                    "evidence",
                    encoding="utf-8",
                )
                return {"evidence_ref": "long-result.json"}

            worker = SupervisedAgentWorker(
                federation,
                agent="ClaudeCode",
                handler=handler,
                poll_seconds=0.05,
                worker_id="claude-long-worker",
            )
            task = await federation.enqueue_task(
                task_type="ENGINEERING",
                payload={},
                correlation_id="worker-long-claim",
                assigned_agent="ClaudeCode",
            )
            await worker.start()
            try:
                await asyncio.wait_for(started.wait(), timeout=1)
                await asyncio.sleep(0.4)
                self.assertEqual(await federation.recover_stale_tasks(), ())
                for _ in range(30):
                    row = federation._load_tasks()[0]
                    if row["status"] == "COMPLETED":
                        break
                    await asyncio.sleep(0.05)
                row = federation._load_tasks()[0]
                self.assertEqual(row["task_id"], task.task_id)
                self.assertEqual(row["status"], "COMPLETED")
                self.assertEqual(row["completed_by_worker_id"], "claude-long-worker")
            finally:
                await worker.stop()

    async def test_stopping_in_process_worker_requeues_its_claim(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                task_path=f"{td}/tasks.json",
                config_hash="cfg",
                source_hash="src",
            )
            started = asyncio.Event()

            async def handler(task):
                started.set()
                await asyncio.Event().wait()

            worker = SupervisedAgentWorker(
                federation,
                agent="ClaudeCode",
                handler=handler,
                poll_seconds=0.05,
                worker_id="claude-cancel-worker",
            )
            task = await federation.enqueue_task(
                task_type="ENGINEERING",
                payload={},
                correlation_id="worker-cancel-claim",
                assigned_agent="ClaudeCode",
            )
            await worker.start()
            await asyncio.wait_for(started.wait(), timeout=1)
            await worker.stop()
            stored = next(
                row for row in federation._load_tasks()
                if row["task_id"] == task.task_id
            )
            self.assertEqual(stored["status"], "PENDING")
            self.assertNotIn("claim_worker_id", stored)
            self.assertNotIn("claim_token_sha256", stored)

    async def test_worker_failure_is_acknowledged_as_failed_not_success(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                task_path=f"{td}/tasks.json",
                config_hash="cfg",
                source_hash="src",
            )

            async def handler(task):
                raise RuntimeError("provider unavailable")

            worker = SupervisedAgentWorker(
                federation, agent="KimiK3", handler=handler, poll_seconds=0.05
            )
            task = await federation.enqueue_task(
                task_type="RESEARCH",
                payload={},
                correlation_id="worker-2",
                assigned_agent="KimiK3",
            )
            await worker.start()
            for _ in range(30):
                rows = federation._load_tasks()
                if rows and rows[0]["status"] == "FAILED":
                    break
                await __import__("asyncio").sleep(0.05)

            self.assertEqual(federation._load_tasks()[0]["status"], "FAILED")
            self.assertEqual(
                federation._load_tasks()[0]["result"],
                {"error_class": "RuntimeError"},
            )
            failures = [
                m for m in federation.messages_for("AURELIA")
                if m["message_type"] == "WORKER_FAILURE"
                and m["payload"]["task_id"] == task.task_id
            ]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0]["payload"]["error_class"], "RuntimeError")
            self.assertNotIn("provider unavailable", str(failures[0]["payload"]))
            await worker.stop()


if __name__ == "__main__":
    unittest.main()
