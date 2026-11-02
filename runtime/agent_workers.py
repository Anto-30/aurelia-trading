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
    """Maintains local advisory-worker leases without executing unverified commands.

    A configured command is only a declaration. There is currently no versioned
    IPC/task-response protocol or authenticated provider handshake, so launching
    arbitrary commands would be both unverifiable and unsafe: subprocesses would
    otherwise inherit broker and deployment credentials from the parent process.

    Until a reviewed worker protocol exists, tasks are explicitly BLOCKED and
    the federation emits CONNECTOR_REQUIRED. This supervisor has no capital
    authority and never claims that a provider is authenticated.
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
    def _command_configured(cls, agent: str) -> bool:
        return bool(os.getenv(cls._env_name(agent), "").strip())

    async def _worker(self, spec: AgentWorkerSpec) -> None:
        worker_id = f"agent-worker:{spec.agent}:{os.getpid()}"
        command_configured = self._command_configured(spec.agent)
        provider_session = (
            "COMMAND_CONFIGURED_PROTOCOL_UNVERIFIED"
            if command_configured
            else "NOT_CONFIGURED"
        )
        connector_reason = (
            "PROVIDER_WORKER_PROTOCOL_NOT_IMPLEMENTED"
            if command_configured
            else "NO_AUTHENTICATED_PROVIDER_COMMAND"
        )
        status_published = False

        while self._running:
            try:
                if not status_published:
                    await self.federation.publish(
                        sender="AURELIA",
                        recipients=(spec.agent,),
                        message_type="CONNECTOR_STATUS",
                        payload={
                            "agent": spec.agent,
                            "worker_runtime": "LOCAL_FEDERATED_WORKER",
                            "provider_session": provider_session,
                            "provider_authentication": "NOT_VERIFIED",
                            "worker_protocol": "NOT_IMPLEMENTED",
                            "capital_authority": False,
                            "connector_command_env": spec.command_env,
                            "tools_skills_plugins": "ORCHESTRATOR_CONTROLLED",
                        },
                        correlation_id=f"connector-status:{spec.agent}",
                        priority=60,
                        requires_response=False,
                    )
                    status_published = True

                await self.federation.heartbeat(
                    spec.agent,
                    worker_id=worker_id,
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
                    await self.federation.complete_task(
                        task.task_id,
                        agent=spec.agent,
                        status="BLOCKED",
                    )
                    await self.federation.publish(
                        sender="AURELIA",
                        recipients=(spec.agent,),
                        message_type="CONNECTOR_REQUIRED",
                        payload={
                            "task_id": task.task_id,
                            "reason": connector_reason,
                            "provider_authentication": "NOT_VERIFIED",
                            "worker_protocol": "NOT_IMPLEMENTED",
                            "tools_skills_plugins": "ORCHESTRATOR_CONTROLLED",
                            "capital_authority": False,
                        },
                        correlation_id=task.correlation_id,
                        priority=95,
                        requires_response=False,
                    )
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
                await asyncio.sleep(max(1.0, self.interval_seconds))

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
