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
            seen = []

            async def handler(task):
                seen.append(task.task_id)
                return {"accepted": True}

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
            await worker.stop()
            self.assertEqual(worker.status.state, "STOPPED")

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
            failures = [
                m for m in federation.messages_for("AURELIA")
                if m["message_type"] == "WORKER_FAILURE"
                and m["payload"]["task_id"] == task.task_id
            ]
            self.assertEqual(len(failures), 1)
            await worker.stop()


if __name__ == "__main__":
    unittest.main()
