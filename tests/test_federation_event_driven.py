from __future__ import annotations

import asyncio
import unittest

from runtime.agent_federation import AgentFederationSupervisor


class FakeFederation:
    def __init__(self):
        self.published: list[dict] = []
        self._stale_notified: set[str] = set()

    def active_agents(self):
        return ("AgentA", "AgentB")

    async def publish(self, **kwargs):
        self.published.append(kwargs)
        return kwargs

    async def recover_stale_tasks(self):
        return ()

    def stale_agents(self):
        return ()

    def _append(self, event_type, payload, correlation_id):
        return None


class FederationEventDrivenTests(unittest.TestCase):
    def test_no_events_produce_no_agent_dispatch(self) -> None:
        async def run() -> None:
            queue: asyncio.Queue = asyncio.Queue()
            federation = FakeFederation()
            supervisor = AgentFederationSupervisor(
                federation,
                agents=("AgentA", "AgentB"),
                event_queue=queue,
                heartbeat_seconds=300.0,
            )
            supervisor.start()
            await asyncio.sleep(0.05)
            self.assertEqual(federation.published, [])
            await supervisor.stop()

        asyncio.run(run())

    def test_strategy_signal_triggers_exactly_one_dispatch_cycle(self) -> None:
        async def run() -> None:
            queue: asyncio.Queue = asyncio.Queue()
            federation = FakeFederation()
            supervisor = AgentFederationSupervisor(
                federation,
                agents=("AgentA", "AgentB"),
                event_queue=queue,
                heartbeat_seconds=300.0,
            )
            supervisor.start()
            await queue.put({
                "event_type": "STRATEGY_SIGNAL_GENERATED",
                "timestamp": "2026-10-07T00:00:00+00:00",
                "strategy": "test",
            })
            await queue.join()
            await asyncio.sleep(0.01)
            self.assertEqual(len(federation.published), 1)
            self.assertEqual(
                federation.published[0]["message_type"],
                "FEDERATION_TRIGGER",
            )
            await supervisor.stop()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
