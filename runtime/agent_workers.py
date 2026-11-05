from __future__ import annotations

import asyncio
import os
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from runtime.agent_federation import PersistentAgentFederation
from runtime.agents.task_protocol import (
    MAX_MESSAGE_BYTES,
    ProtocolError,
    build_task_message,
    decode_message,
    encode_message,
    persist_evidence,
    validate_hello,
    validate_task_result,
)


@dataclass(frozen=True)
class AgentWorkerSpec:
    agent: str
    command_env: str


class AgentWorkerSupervisor:
    """Runs advisory workers through an attributable, bounded JSONL channel.

    A successful handshake proves only that a local process speaks this
    protocol. It does not prove the identity/authentication of an upstream
    model provider. The process receives an allow-listed environment, a
    private working directory, and no broker/API secrets from AURELIA.
    """

    _SAFE_ENV_KEYS = (
        "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "SYSTEMROOT",
        "WINDIR", "TMP", "TEMP", "TMPDIR",
    )

    def __init__(
        self,
        federation: PersistentAgentFederation,
        *,
        agents: Iterable[str],
        interval_seconds: float = 10.0,
        startup_timeout_seconds: float = 10.0,
        task_timeout_seconds: float = 300.0,
        evidence_root: str | Path | None = None,
    ) -> None:
        self.federation = federation
        self.agents = tuple(sorted(set(agents)))
        self.interval_seconds = max(0.05, float(interval_seconds))
        self.startup_timeout_seconds = max(0.1, float(startup_timeout_seconds))
        self.task_timeout_seconds = max(0.1, float(task_timeout_seconds))
        configured_root = evidence_root or federation.performance_evaluator.evidence_root
        self.evidence_root = Path(configured_root)
        self.federation.performance_evaluator.evidence_root = self.evidence_root
        self.worker_home_root = self.evidence_root / "worker-homes"
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

    def _worker_environment(self, agent: str) -> tuple[dict[str, str], Path]:
        safe_agent = "".join(c if c.isalnum() or c in "-_" else "_" for c in agent)
        home = self.worker_home_root / safe_agent
        home.mkdir(parents=True, exist_ok=True)
        environment = {
            key: os.environ[key]
            for key in self._SAFE_ENV_KEYS
            if os.environ.get(key)
        }
        environment.update({
            "HOME": str(home.resolve()),
            "AURELIA_AGENT_NAME": agent,
            "AURELIA_WORKER_PROTOCOL_VERSION": "1",
            "PYTHONUNBUFFERED": "1",
        })
        return environment, home

    @staticmethod
    async def _read_message(reader: asyncio.StreamReader) -> dict:
        try:
            line = await reader.readline()
        except (ValueError, asyncio.LimitOverrunError) as exc:
            raise ProtocolError("WORKER_MESSAGE_LINE_TOO_LARGE") from exc
        if not line:
            raise ProtocolError("WORKER_STDOUT_CLOSED")
        return decode_message(line, max_bytes=MAX_MESSAGE_BYTES)

    @staticmethod
    async def _send_message(writer: asyncio.StreamWriter, message: dict) -> None:
        writer.write(encode_message(message))
        await writer.drain()

    async def _heartbeat(self, agent: str, worker_id: str) -> None:
        await self.federation.heartbeat(
            agent,
            worker_id=worker_id,
            origin="WORKER",
        )

    async def _await_task_result(
        self,
        *,
        process: asyncio.subprocess.Process,
        task,
        worker_id: str,
    ):
        if process.stdin is None or process.stdout is None or task.claim_token is None:
            raise ProtocolError("WORKER_PROTOCOL_STREAM_UNAVAILABLE")
        await self._send_message(
            process.stdin,
            build_task_message(task, worker_id=worker_id),
        )
        reader_task = asyncio.create_task(self._read_message(process.stdout))
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.task_timeout_seconds
        try:
            while not reader_task.done():
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise ProtocolError("TASK_RESULT_TIMEOUT")
                try:
                    await asyncio.wait_for(
                        asyncio.shield(reader_task),
                        timeout=min(self.interval_seconds, remaining),
                    )
                except asyncio.TimeoutError:
                    if process.returncode is not None:
                        raise ProtocolError("WORKER_EXITED_BEFORE_TASK_RESULT")
                    await self._heartbeat(task.assigned_agent, worker_id)
                    renewed = await self.federation.renew_task_claim(
                        task.task_id,
                        agent=task.assigned_agent,
                        worker_id=worker_id,
                        claim_token=task.claim_token,
                    )
                    if not renewed:
                        raise ProtocolError("TASK_CLAIM_RENEWAL_REJECTED")
            message = reader_task.result()
            return validate_task_result(
                message,
                expected_agent=task.assigned_agent,
                expected_task_id=task.task_id,
                expected_claim_token=task.claim_token,
            )
        finally:
            if not reader_task.done():
                reader_task.cancel()
                try:
                    await reader_task
                except (asyncio.CancelledError, Exception):
                    pass

    async def _publish_unconfigured(self, agent: str) -> None:
        await self.federation.publish(
            sender="AURELIA",
            recipients=(agent,),
            message_type="CONNECTOR_REQUIRED",
            payload={
                "agent": agent,
                "reason": "NO_CONFIGURED_WORKER_COMMAND",
                "worker_protocol": "AURELIA_AGENT_JSONL_V1",
                "provider_authentication": "NOT_VERIFIED",
                "capital_authority": False,
            },
            correlation_id=f"connector-required:{agent}",
            priority=95,
            requires_response=False,
        )

    async def _worker(self, spec: AgentWorkerSpec) -> None:
        restart_delay = max(1.0, self.interval_seconds)
        restart_count = 0
        while self._running:
            process = None
            claim = None
            worker_id = ""
            try:
                command = self._command(spec.agent)
                if not command:
                    await self._publish_unconfigured(spec.agent)
                    await asyncio.sleep(self.interval_seconds)
                    continue

                environment, worker_home = self._worker_environment(spec.agent)
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    cwd=str(worker_home),
                    env=environment,
                    limit=MAX_MESSAGE_BYTES + 1,
                )
                if process.stdin is None or process.stdout is None:
                    raise ProtocolError("WORKER_PROTOCOL_STREAM_UNAVAILABLE")
                hello = await asyncio.wait_for(
                    self._read_message(process.stdout),
                    timeout=self.startup_timeout_seconds,
                )
                validate_hello(hello, expected_agent=spec.agent)
                worker_id = (
                    f"agent-worker:{spec.agent}:{os.getpid()}:{process.pid}:r{restart_count}"
                )
                await self.federation.publish(
                    sender="AURELIA",
                    recipients=(spec.agent,),
                    message_type="CONNECTOR_STATUS",
                    payload={
                        "agent": spec.agent,
                        "worker_runtime": "LOCAL_JSONL_PROTOCOL_WORKER",
                        "worker_id": worker_id,
                        "worker_protocol": "AURELIA_AGENT_JSONL_V1",
                        "provider_authentication": "NOT_VERIFIED_BY_PROTOCOL",
                        "capital_authority": False,
                    },
                    correlation_id=f"connector-status:{spec.agent}:{worker_id}",
                    priority=60,
                    requires_response=False,
                )

                while self._running:
                    if process.returncode is not None:
                        raise ProtocolError("WORKER_PROCESS_EXITED")
                    await self._heartbeat(spec.agent, worker_id)
                    await self.federation.recover_stale_tasks()
                    claim = await self.federation.claim_task(
                        spec.agent,
                        worker_id=worker_id,
                    )
                    if claim is None:
                        await asyncio.sleep(self.interval_seconds)
                        continue

                    await self.federation.publish(
                        sender="AURELIA",
                        recipients=(spec.agent,),
                        message_type="AGENT_TASK_CLAIMED",
                        payload={
                            "task_id": claim.task_id,
                            "task_type": claim.task_type,
                            "worker_id": worker_id,
                            "worker_protocol": "AURELIA_AGENT_JSONL_V1",
                            "capital_authority": False,
                        },
                        correlation_id=claim.correlation_id,
                        priority=claim.priority,
                        requires_response=True,
                    )
                    try:
                        outcome = await self._await_task_result(
                            process=process,
                            task=claim,
                            worker_id=worker_id,
                        )
                        evidence_record = {
                            "schema": "aurelia.agent_task_evidence.v1",
                            "protocol_version": 1,
                            "task_id": claim.task_id,
                            "task_type": claim.task_type,
                            "agent": spec.agent,
                            "worker_id": worker_id,
                            "status": outcome.status,
                            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                            "task_payload": claim.payload,
                            "worker_result": outcome.result,
                            "worker_evidence": outcome.evidence,
                            "attribution": {
                                "transport": "SUPERVISOR_CHILD_STDOUT",
                                "claim_capability_validated": True,
                                "provider_authentication": False,
                                "content_truth_independently_verified": False,
                            },
                        }
                        artifact = persist_evidence(self.evidence_root, evidence_record)
                        # Provider assertions are retained as a nested report.
                        # They are not accepted as deterministic verification flags.
                        evaluation_result = {
                            "worker_report": outcome.result,
                            "verified": False,
                            "regression_free": False,
                            "reproducible": False,
                            "efficient": False,
                            "handoff_clean": False,
                        }
                        completed = await self.federation.complete_task(
                            claim.task_id,
                            agent=spec.agent,
                            status=outcome.status,
                            evidence_ref=artifact.relative_ref,
                            result=evaluation_result,
                            worker_id=worker_id,
                            claim_token=claim.claim_token,
                        )
                        if not completed:
                            raise ProtocolError("TASK_COMPLETION_REJECTED")
                        claim = None
                    except Exception as exc:
                        await self.federation.release_task_claim(
                            claim.task_id,
                            agent=spec.agent,
                            worker_id=worker_id,
                            claim_token=claim.claim_token,
                            reason=type(exc).__name__,
                        )
                        claim = None
                        raise
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.federation.publish(
                    sender="AURELIA",
                    recipients=(spec.agent,),
                    message_type="WORKER_PROTOCOL_ERROR",
                    payload={
                        "agent": spec.agent,
                        "worker_runtime": "LOCAL_JSONL_PROTOCOL_WORKER",
                        "error_class": type(exc).__name__,
                        "error_code": str(exc)[:100] if isinstance(exc, ProtocolError) else "WORKER_RUNTIME_FAILURE",
                        "restart_policy": "RESTART_WHILE_RUNTIME_HEALTHY",
                        "provider_authentication": "NOT_VERIFIED",
                        "capital_authority": False,
                    },
                    correlation_id=f"worker-protocol-error:{spec.agent}:{restart_count}",
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
