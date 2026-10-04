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


if __name__ == "__main__":
    unittest.main()
