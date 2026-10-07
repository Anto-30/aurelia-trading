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
        restart_delay = max(1.0, self.interval_seconds)
        restart_count = 0
        while self._running:
            process = None
            try:
                if command:
                    process = await asyncio.create_subprocess_exec(*command)
                await self.federation.publish(
                    sender="AURELIA",
                    recipients=(spec.agent,),
                    message_type="CONNECTOR_STATUS",
                    payload={
                        "agent": spec.agent,
                        "worker_runtime": "LOCAL_FEDERATED_WORKER",
                        "provider_session": "CONFIGURED_COMMAND" if command else "NOT_CONFIGURED",
                        "capital_authority": False,
                        "connector_command_env": self._env_name(spec.agent),
                        "tools_skills_plugins": "ORCHESTRATOR_CONTROLLED",
                    },
                    correlation_id=f"connector-status:{spec.agent}",
                    priority=60,
                    requires_response=False,
                )
                while self._running:
                    await self.federation.heartbeat(
                        spec.agent,
                        worker_id=f"{worker_id}:r{restart_count}",
                        origin="WORKER",
                    )
                    task = await self.federation.claim_task(spec.agent)
                    if task is not None:
                        await self.federation.publish(
                            sender="AURELIA",
                            recipients=(spec.agent,),
                            message_type="AGENT_TASK_CLAIMED",
                            payload={
                                "task_id": task.task_id,
                                "task_type": task.task_type,
                                "payload": task.payload,
                                "tools_skills_plugins": "ORCHESTRATOR_CONTROLLED",
                                "capital_authority": False,
                            },
                            correlation_id=task.correlation_id,
                            priority=task.priority,
                            requires_response=True,
                        )
                        # A configured external worker owns execution. The local
                        # supervisor never fabricates a provider result. It leaves
                        # the task CLAIMED so the provider worker can complete it;
                        # stale claims are requeued by the federation.
                        if process is None:
                            await self.federation.complete_task(
                                task.task_id, agent=spec.agent, status="BLOCKED"
                            )
                            await self.federation.publish(
                                sender="AURELIA",
                                recipients=(spec.agent,),
                                message_type="CONNECTOR_REQUIRED",
                                payload={
                                    "task_id": task.task_id,
                                    "reason": "NO_AUTHENTICATED_PROVIDER_COMMAND",
                                    "tools_skills_plugins": "ORCHESTRATOR_CONTROLLED",
                                    "capital_authority": False,
                                },
                                correlation_id=task.correlation_id,
                                priority=95,
                                requires_response=False,
                            )
                    if process is not None and process.returncode is not None:
                        break
                    await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.federation.publish(
                    sender="AURELIA",
                    recipients=(spec.agent,),
                    message_type="WORKER_RUNTIME_ERROR",
                    payload={
                        "agent": spec.agent,
                        "worker_runtime": "LOCAL_FEDERATED_WORKER",
                        "error_class": type(exc).__name__,
                        "restart_policy": "ALWAYS_WHILE_RUNTIME_HEALTHY",
                        "capital_authority": False,
                    },
                    correlation_id=f"worker-error:{spec.agent}",
                    priority=95,
                    requires_response=False,
                )
            finally:
                if process is not None and process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
            if not self._running:
                break
            restart_count += 1
            await asyncio.sleep(restart_delay)

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
