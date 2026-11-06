from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Iterable

from runtime.agent_federation import PersistentAgentFederation


@dataclass(frozen=True)
class AgentWorkerSpec:
    agent: str
    command_env: str


class AgentWorkerSupervisor:
    """Fail-closed connector supervisor.

    No provider process is started and no worker lease is emitted until the
    JSONL claim/result/evidence protocol and OS-level sandbox are integrated
    and independently verified. A configured command is not provider proof.
    """

    def __init__(
        self,
        federation: PersistentAgentFederation,
        *,
        agents: Iterable[str],
        interval_seconds: float = 10.0,
    ) -> None:
        self.federation = federation
        self.agents = tuple(sorted(set(agents)))
        self.interval_seconds = max(2.0, float(interval_seconds))
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._running = False

    @staticmethod
    def _env_name(agent: str) -> str:
        return "AURELIA_AGENT_" + "".join(
            c if c.isalnum() else "_" for c in agent.upper()
        ) + "_COMMAND"

    async def _worker(self, spec: AgentWorkerSpec) -> None:
        if not self._running:
            return

        command_configured = spec.command_env in os.environ
        reason = (
            "JSONL_PROTOCOL_AND_OS_SANDBOX_NOT_INTEGRATED"
            if command_configured
            else "NO_AUTHENTICATED_PROVIDER_COMMAND"
        )
        provider_session = (
            "COMMAND_CONFIGURED_BUT_BLOCKED"
            if command_configured
            else "NOT_CONFIGURED"
        )

        await self.federation.publish(
            sender="AURELIA",
            recipients=(spec.agent,),
            message_type="CONNECTOR_STATUS",
            payload={
                "agent": spec.agent,
                "worker_runtime": "DISABLED_UNTIL_JSONL_AND_OS_SANDBOX",
                "provider_session": provider_session,
                "provider_authenticated": False,
                "process_started": False,
                "worker_lease_emitted": False,
                "capital_authority": False,
            },
            correlation_id=f"connector-status:{spec.agent}",
            priority=60,
            requires_response=False,
        )
        await self.federation.publish(
            sender="AURELIA",
            recipients=(spec.agent,),
            message_type="CONNECTOR_REQUIRED",
            payload={
                "agent": spec.agent,
                "reason": reason,
                "process_started": False,
                "worker_lease_emitted": False,
                "capital_authority": False,
            },
            correlation_id=f"connector-required:{spec.agent}",
            priority=95,
            requires_response=False,
        )

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        for agent in self.agents:
            if agent == "AURELIA":
                continue
            spec = AgentWorkerSpec(agent=agent, command_env=self._env_name(agent))
            self._tasks[agent] = asyncio.create_task(
                self._worker(spec), name=f"agent-worker-gate:{agent}"
            )

    async def stop(self) -> None:
        self._running = False
        tasks = list(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
