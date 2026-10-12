from __future__ import annotations

import asyncio
import json
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
        task_timeout_seconds: float = 120.0,
    ) -> None:
        self.federation = federation
        self.agents = tuple(sorted(set(agents)))
        self.interval_seconds = max(2.0, float(interval_seconds))
        self.task_timeout_seconds = max(1.0, float(task_timeout_seconds))
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
                    process = await asyncio.create_subprocess_exec(
                        *command,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
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
                if process is None:
                    # A local supervisor loop is not proof that the provider agent
                    # is connected. Do not emit an agent heartbeat or claim work
                    # until an explicitly configured provider command is running.
                    await self.federation.publish(
                        sender="AURELIA",
                        recipients=(spec.agent,),
                        message_type="CONNECTOR_REQUIRED",
                        payload={
                            "agent": spec.agent,
                            "reason": "NO_AUTHENTICATED_PROVIDER_COMMAND",
                            "provider_session": "NOT_CONFIGURED",
                            "capital_authority": False,
                        },
                        correlation_id=f"connector-required:{spec.agent}",
                        priority=95,
                        requires_response=False,
                    )
                    await asyncio.sleep(self.interval_seconds)
                    continue
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
                        # Provider commands must implement a JSON Lines protocol:
                        # one request line in, one result line out. Process presence
                        # alone is not task completion evidence.
                        if process is None or process.stdin is None or process.stdout is None:
                            await self.federation.complete_task(
                                task.task_id, agent=spec.agent, status="BLOCKED",
                                result={"reason": "PROVIDER_STREAMS_UNAVAILABLE"},
                            )
                        else:
                            request = {
                                "schema": "aurelia.agent_task_request.v1",
                                "task_id": task.task_id,
                                "correlation_id": task.correlation_id,
                                "task_type": task.task_type,
                                "payload": task.payload,
                                "deadline_seconds": self.task_timeout_seconds,
                                "authorized_scope": "ADVISORY_ENGINEERING_ONLY",
                                "capital_authority": False,
                            }
                            try:
                                process.stdin.write((json.dumps(request, sort_keys=True) + "\\n").encode("utf-8"))
                                await process.stdin.drain()
                                raw_result = await asyncio.wait_for(
                                    process.stdout.readline(), timeout=self.task_timeout_seconds
                                )
                                if not raw_result:
                                    raise ValueError("PROVIDER_RESULT_EOF")
                                result_message = json.loads(raw_result.decode("utf-8"))
                                if not isinstance(result_message, dict):
                                    raise ValueError("PROVIDER_RESULT_NOT_OBJECT")
                                if result_message.get("schema") != "aurelia.agent_task_result.v1":
                                    raise ValueError("PROVIDER_RESULT_SCHEMA_MISMATCH")
                                if result_message.get("task_id") != task.task_id:
                                    raise ValueError("PROVIDER_RESULT_TASK_ID_MISMATCH")
                                status = result_message.get("status")
                                if status not in {"COMPLETED", "FAILED", "BLOCKED"}:
                                    raise ValueError("PROVIDER_RESULT_STATUS_INVALID")
                                evidence_ref = result_message.get("evidence_ref", "")
                                if not isinstance(evidence_ref, str):
                                    raise ValueError("PROVIDER_EVIDENCE_REF_INVALID")
                                result_body = result_message.get("result", {})
                                if not isinstance(result_body, dict):
                                    raise ValueError("PROVIDER_RESULT_BODY_INVALID")
                                await self.federation.complete_task(
                                    task.task_id, agent=spec.agent, status=status,
                                    evidence_ref=evidence_ref, result=result_body,
                                )
                            except (asyncio.TimeoutError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                                await self.federation.complete_task(
                                    task.task_id, agent=spec.agent, status="FAILED",
                                    result={"reason": str(exc)[:160], "error_class": type(exc).__name__},
                                )
                            await self.federation.publish(
                                sender="AURELIA",
                                recipients=(spec.agent,),
                                message_type="AGENT_TASK_RESULT_RECORDED",
                                payload={"task_id": task.task_id, "capital_authority": False},
                                correlation_id=task.correlation_id,
                                priority=70,
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
