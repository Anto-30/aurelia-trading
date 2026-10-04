import asyncio
import tempfile
import unittest

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
            self.assertTrue(await federation.complete_task(high.task_id, agent="GoogleAgentSkills"))
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

    async def test_stale_agent_is_detectable_after_lease_expiry(self):
        with tempfile.TemporaryDirectory() as td:
            federation = PersistentAgentFederation(
                journal_path=f"{td}/events.ndjson",
                lease_path=f"{td}/leases.json",
                config_hash="cfg",
                source_hash="src",
                lease_seconds=5,
            )
            await federation.heartbeat("ClaudeCode")
            data = federation._load_leases()
            data["ClaudeCode"]["expires_at"] = "2000-01-01T00:00:00+00:00"
            federation._save_leases(data)
            self.assertIn("ClaudeCode", federation.stale_agents())
            self.assertNotIn("ClaudeCode", federation.active_agents())


if __name__ == "__main__":
    unittest.main()
