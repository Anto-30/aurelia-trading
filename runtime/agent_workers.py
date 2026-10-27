from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Iterable, Mapping

from runtime.agent_federation import PersistentAgentFederation


@dataclass(frozen=True)
class AgentWorkerSpec:
    agent: str
    command_env: str
    healthcheck_env: str


class AgentWorkerSupervisor:
    """Supervise configured advisory worker processes without synthetic liveness.

    A roster entry is not a process, and a process command alone is not readiness.
    An agent gets a lease only while its configured worker process is alive and its
    operator-supplied readiness command exits successfully. The readiness command
    must verify the provider/runtime state required by that agent (including
    authentication if required). The supervisor does not infer authentication from
    a non-empty key, a process name, or a successful process launch.

    Commands must be trusted local adapters that implement the AURELIA worker
    protocol and watch the federation files exposed in their environment. Their
    stdout/stderr are discarded to avoid leaking secrets into logs. No worker
    receives capital authority.
    """

    def __init__(
        self,
        federation: PersistentAgentFederation,
        *,
        agents: Iterable[str],
        interval_seconds: float = 10.0,
        healthcheck_timeout_seconds: float = 5.0,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.federation = federation
        self.environment = dict(os.environ if env is None else env)
        self.agents = tuple(sorted(set(agents)))
        self.interval_seconds = max(0.1, float(interval_seconds))
        self.healthcheck_timeout_seconds = max(0.5, float(healthcheck_timeout_seconds))
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._running = False

    @staticmethod
    def _env_name(agent: str) -> str:
        return "AURELIA_AGENT_" + "".join(
            c if c.isalnum() else "_" for c in agent.upper()
        ) + "_COMMAND"

    @classmethod
    def _healthcheck_env_name(cls, agent: str) -> str:
        return cls._env_name(agent).removesuffix("_COMMAND") + "_HEALTHCHECK_COMMAND"

    def _parse_command(self, env_name: str) -> list[str] | None:
        raw = str(self.environment.get(env_name, "")).strip()
        if not raw:
            return None
        try:
            command = shlex.split(raw)
        except ValueError:
            return None
        return command or None

    def _command(self, agent: str) -> list[str] | None:
        return self._parse_command(self._env_name(agent))

    def _healthcheck_command(self, agent: str) -> list[str] | None:
        return self._parse_command(self._healthcheck_env_name(agent))

    async def _run_healthcheck(self, command: list[str]) -> bool:
        """Run an output-suppressed, bounded readiness command."""
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            return_code = await asyncio.wait_for(
                process.wait(), timeout=self.healthcheck_timeout_seconds
            )
            return return_code == 0
        except (OSError, ValueError, asyncio.TimeoutError):
            if process is not None and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
            return False

    async def _publish_connector_required(self, agent: str, reason: str) -> None:
        await self.federation.revoke_lease(agent, reason=reason)
        await self.federation.publish(
            sender="AURELIA",
            recipients=(agent,),
            message_type="CONNECTOR_REQUIRED",
            payload={
                "agent": agent,
                "reason": reason,
                "worker_process_status": "NOT_STARTED",
                "readiness_probe": "NOT_CONFIGURED",
                "provider_session": "UNKNOWN",
                "tools_skills_plugins": "ORCHESTRATOR_CONTROLLED",
                "capital_authority": False,
                "secret_values_emitted": False,
            },
            correlation_id=f"connector-required:{agent}:{reason}",
            priority=95,
            requires_response=False,
        )

    async def _worker(self, spec: AgentWorkerSpec) -> None:
        worker_id_base = f"agent-worker:{spec.agent}:{os.getpid()}"
        restart_delay = max(1.0, self.interval_seconds)
        restart_count = 0

        while self._running:
            process = None
            command = self._command(spec.agent)
            healthcheck = self._healthcheck_command(spec.agent)
            if command is None:
                await self._publish_connector_required(spec.agent, "WORKER_COMMAND_MISSING")
                try:
                    await asyncio.sleep(restart_delay)
                except asyncio.CancelledError:
                    raise
                continue
            if healthcheck is None:
                await self._publish_connector_required(
                    spec.agent, "WORKER_HEALTHCHECK_COMMAND_MISSING"
                )
                try:
                    await asyncio.sleep(restart_delay)
                except asyncio.CancelledError:
                    raise
                continue

            worker_id = f"{worker_id_base}:r{restart_count}"
            try:
                worker_env = dict(self.environment)
                worker_env.update({
                    "AURELIA_AGENT_ID": spec.agent,
                    "AURELIA_AGENT_WORKER_PROTOCOL": "PERSISTENT_FEDERATION_JSON_V1",
                    "AURELIA_AGENT_FEDERATION_TASK_PATH": str(self.federation.task_path),
                    "AURELIA_AGENT_FEDERATION_JOURNAL_PATH": str(self.federation.journal.path),
                    "AURELIA_AGENT_FEDERATION_LEASE_PATH": str(self.federation.lease_path),
                })
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=worker_env,
                )
                status_published = False
                while self._running:
                    if process.returncode is not None:
                        await self.federation.revoke_lease(
                            spec.agent, worker_id=worker_id, reason="WORKER_PROCESS_EXITED"
                        )
                        await self.federation.publish(
                            sender="AURELIA",
                            recipients=(spec.agent,),
                            message_type="CONNECTOR_UNHEALTHY",
                            payload={
                                "agent": spec.agent,
                                "reason": "WORKER_PROCESS_EXITED",
                                "worker_return_code": process.returncode,
                                "capital_authority": False,
                            },
                            correlation_id=f"worker-exit:{spec.agent}:{restart_count}",
                            priority=95,
                            requires_response=False,
                        )
                        break

                    if not await self._run_healthcheck(healthcheck):
                        await self.federation.revoke_lease(
                            spec.agent, worker_id=worker_id, reason="HEALTHCHECK_FAILED"
                        )
                        await self.federation.publish(
                            sender="AURELIA",
                            recipients=(spec.agent,),
                            message_type="CONNECTOR_UNHEALTHY",
                            payload={
                                "agent": spec.agent,
                                "reason": "HEALTHCHECK_FAILED",
                                "readiness_probe": "FAIL",
                                "capital_authority": False,
                                "secret_values_emitted": False,
                            },
                            correlation_id=f"healthcheck-failed:{spec.agent}:{restart_count}",
                            priority=95,
                            requires_response=False,
                        )
                        break

                    if not status_published:
                        await self.federation.publish(
                            sender="AURELIA",
                            recipients=(spec.agent,),
                            message_type="CONNECTOR_STATUS",
                            payload={
                                "agent": spec.agent,
                                "worker_runtime": "LOCAL_FEDERATED_WORKER",
                                "worker_process_status": "RUNNING",
                                "readiness_probe": "PASS",
                                "healthcheck_command_env": spec.healthcheck_env,
                                "provider_session": "NOT_INDEPENDENTLY_VERIFIED",
                                "capital_authority": False,
                                "tools_skills_plugins": "ORCHESTRATOR_CONTROLLED",
                                "secret_values_emitted": False,
                            },
                            correlation_id=f"connector-status:{spec.agent}",
                            priority=60,
                            requires_response=False,
                        )
                        status_published = True

                    # Leases only mean the configured worker is alive and its
                    # operator-defined healthcheck currently passes. They do not
                    # grant authority or independently prove provider correctness.
                    await self.federation.heartbeat(
                        spec.agent, worker_id=worker_id, origin="WORKER"
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
                                "worker_protocol": "PERSISTENT_FEDERATION_JSON_V1",
                                "task_store_path": str(self.federation.task_path),
                                "capital_authority": False,
                            },
                            correlation_id=task.correlation_id,
                            priority=task.priority,
                            requires_response=True,
                        )
                        # Only the configured worker adapter can perform the task
                        # and acknowledge completion through the federation API.
                        # A claim by itself is not task completion.
                    try:
                        await asyncio.sleep(self.interval_seconds)
                    except asyncio.CancelledError:
                        raise
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.federation.revoke_lease(
                    spec.agent, worker_id=worker_id, reason="WORKER_RUNTIME_ERROR"
                )
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
                        "secret_values_emitted": False,
                    },
                    correlation_id=f"worker-error:{spec.agent}:{restart_count}",
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
            spec = AgentWorkerSpec(
                agent=agent,
                command_env=self._env_name(agent),
                healthcheck_env=self._healthcheck_env_name(agent),
            )
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
