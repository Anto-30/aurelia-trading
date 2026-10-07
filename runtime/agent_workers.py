from __future__ import annotations

import asyncio
import os
import shlex
from dataclasses import dataclass
from typing import Iterable

from runtime.agent_federation import PersistentAgentFederation


@dataclass(frozen=True)
class AgentWorkerSpec:
    agent: str
    command_env: str


class AgentWorkerSupervisor:
    """Runs real local worker processes for registered advisory agents.

    A worker lease is emitted only by this supervisor's running worker task.
    External provider authentication is never fabricated: each worker may be
    backed by a configured command, and otherwise remains CONNECTOR_REQUIRED.
    No worker can grant capital authority.
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

    @classmethod
    def _command(cls, agent: str) -> list[str] | None:
        raw = os.getenv(cls._env_name(agent), "").strip()
        return shlex.split(raw) if raw else None

    async def _worker(self, spec: AgentWorkerSpec) -> None:
        worker_id = f"agent-worker:{spec.agent}:{os.getpid()}"
        command = self._command(spec.agent)
        if command:
            process = await asyncio.create_subprocess_exec(*command)
            try:
                while self._running:
                    await self.federation.heartbeat(
                        spec.agent, worker_id=worker_id, origin="WORKER"
                    )
                    if process.returncode is not None:
                        break
                    await asyncio.sleep(self.interval_seconds)
            finally:
                if process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
            return

        # No external connector command is configured. Do not impersonate a
        # provider session and do not claim authenticated-provider liveness.
        await self.federation.publish(
            sender="AURELIA",
            recipients=(spec.agent,),
            message_type="CONNECTOR_REQUIRED",
            payload={
                "agent": spec.agent,
                "worker_runtime": "LOCAL_WORKER_SUPERVISOR",
                "provider_session": "NOT_CONFIGURED",
                "capital_authority": False,
                "action_required": self._env_name(spec.agent),
            },
            correlation_id=f"connector-required:{spec.agent}",
            priority=85,
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
                self._worker(spec), name=f"agent-worker:{agent}"
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
