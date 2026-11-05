from __future__ import annotations

import asyncio
import json
import os
import secrets
import shlex
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from runtime.agent_federation import AgentTask, PersistentAgentFederation


WORKER_PROTOCOL = "aurelia.agent-task.v1"
MAX_FRAME_BYTES = 1_048_576
MAX_RESULT_BYTES = 65_536
MAX_SUMMARY_CHARS = 4_096
MAX_ARTIFACT_TYPE_CHARS = 128
AUTHORITY_FIELDS = {
    "capital_authority",
    "final_execution_authorization",
    "live_trading_enabled",
    "order_submission_permitted",
    "live_execution_authority",
}
SENSITIVE_INPUT_FIELDS = {
    "token",
    "secret",
    "password",
    "apikey",
    "authorization",
    "cookie",
    "privatekey",
    "credential",
    "otp",
    "loginid",
    "accounttoken",
    "accesskey",
    "bearer",
}


class WorkerProtocolError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AgentWorkerSpec:
    agent: str
    command_env: str


class AgentWorkerSupervisor:
    """Runs bounded JSONL adapters for advisory/engineering workers only.

    A process receives no inherited broker/cloud/API credentials from the
    supervisor environment. A successful protocol handshake proves only that
    the configured local adapter speaks this contract; it is not proof of an
    external model-provider identity or authentication.
    """

    def __init__(
        self,
        federation: PersistentAgentFederation,
        *,
        agents: Iterable[str],
        interval_seconds: float = 10.0,
        handshake_timeout_seconds: float = 10.0,
        response_timeout_seconds: float = 300.0,
    ) -> None:
        self.federation = federation
        self.agents = tuple(sorted(set(agents)))
        self.interval_seconds = max(0.05, float(interval_seconds))
        self.handshake_timeout_seconds = max(0.1, float(handshake_timeout_seconds))
        self.response_timeout_seconds = max(0.1, float(response_timeout_seconds))
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
        if not raw:
            return None
        try:
            command = shlex.split(raw)
        except ValueError:
            raise WorkerProtocolError("WORKER_COMMAND_SYNTAX_INVALID") from None
        if not command:
            raise WorkerProtocolError("WORKER_COMMAND_EMPTY")
        return command

    @staticmethod
    def _contains_field(value: Any, blocked: set[str]) -> bool:
        if isinstance(value, dict):
            for key, nested in value.items():
                normalized = "".join(c for c in str(key).casefold() if c.isalnum())
                if (
                    normalized in blocked
                    or any(marker in normalized for marker in blocked if len(marker) >= 5)
                    or AgentWorkerSupervisor._contains_field(nested, blocked)
                ):
                    return True
        elif isinstance(value, (list, tuple)):
            return any(
                AgentWorkerSupervisor._contains_field(item, blocked)
                for item in value
            )
        return False

    def _worker_environment(
        self,
        spec: AgentWorkerSpec,
        *,
        worker_id: str,
        session_nonce: str,
        home_dir: str,
    ) -> dict[str, str]:
        # Inherit only runtime essentials. Deny-by-default is intentional:
        # name-based secret filtering is insufficient because CLI credentials
        # are commonly cached below HOME and custom environment variable names
        # cannot be comprehensively enumerated.
        allowed = {
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "TZ",
            "TERM",
            "TMPDIR",
            "TEMP",
            "TMP",
            "PYTHONIOENCODING",
            "PYTHONUTF8",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "REQUESTS_CA_BUNDLE",
        }
        env = {
            key: value for key, value in os.environ.items() if key in allowed
        }
        env.update(
            {
                "HOME": home_dir,
                "USERPROFILE": home_dir,
                "APPDATA": str(Path(home_dir) / "appdata"),
                "LOCALAPPDATA": str(Path(home_dir) / "localappdata"),
                "TMP": str(Path(home_dir) / "tmp"),
                "TEMP": str(Path(home_dir) / "tmp"),
                "TMPDIR": str(Path(home_dir) / "tmp"),
                "AURELIA_WORKER_PROTOCOL": WORKER_PROTOCOL,
                "AURELIA_WORKER_AGENT": spec.agent,
                "AURELIA_WORKER_ID": worker_id,
                "AURELIA_WORKER_SESSION_NONCE": session_nonce,
                "AURELIA_EVIDENCE_ROOT": str(
                    self.federation.performance_evaluator.evidence_root
                ),
            }
        )
        for name in ("appdata", "localappdata", "tmp"):
            (Path(home_dir) / name).mkdir(parents=True, exist_ok=True)
        return env

    @staticmethod
    async def _send_frame(
        process: asyncio.subprocess.Process, value: dict[str, Any]
    ) -> None:
        if process.stdin is None:
            raise WorkerProtocolError("WORKER_STDIN_UNAVAILABLE")
        try:
            frame = (
                json.dumps(
                    value,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
                + b"\n"
            )
        except (TypeError, ValueError):
            raise WorkerProtocolError("WORKER_REQUEST_NOT_JSON_SERIALIZABLE") from None
        if len(frame) > MAX_FRAME_BYTES:
            raise WorkerProtocolError("WORKER_REQUEST_FRAME_TOO_LARGE")
        process.stdin.write(frame)
        try:
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionError, OSError):
            raise WorkerProtocolError("WORKER_STDIN_CLOSED") from None

    @staticmethod
    async def _read_frame(
        process: asyncio.subprocess.Process,
        *,
        timeout_seconds: float,
        max_bytes: int,
        timeout_code: str,
    ) -> dict[str, Any]:
        if process.stdout is None:
            raise WorkerProtocolError("WORKER_STDOUT_UNAVAILABLE")
        try:
            line = await asyncio.wait_for(
                process.stdout.readline(),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise WorkerProtocolError(timeout_code) from None
        except (ValueError, asyncio.LimitOverrunError):
            raise WorkerProtocolError("WORKER_RESPONSE_FRAME_TOO_LARGE") from None
        if not line:
            raise WorkerProtocolError("WORKER_RESPONSE_EOF")
        if len(line) > max_bytes:
            raise WorkerProtocolError("WORKER_RESPONSE_FRAME_TOO_LARGE")

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("DUPLICATE_JSON_KEY")
                value[key] = item
            return value

        try:
            value = json.loads(
                line.decode("utf-8"),
                object_pairs_hook=unique_object,
                parse_constant=lambda _value: (_ for _ in ()).throw(
                    ValueError("NON_FINITE_JSON_NUMBER")
                ),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise WorkerProtocolError("WORKER_RESPONSE_INVALID_JSON") from None
        if not isinstance(value, dict):
            raise WorkerProtocolError("WORKER_RESPONSE_NOT_OBJECT")
        return value

    @classmethod
    def _validate_handshake(
        cls,
        response: dict[str, Any],
        *,
        agent: str,
        worker_id: str,
        session_nonce: str,
    ) -> None:
        if cls._contains_field(response, AUTHORITY_FIELDS):
            raise WorkerProtocolError("WORKER_AUTHORITY_FIELD_FORBIDDEN")
        if set(response) != {
            "protocol", "type", "agent", "worker_id", "session_nonce"
        }:
            raise WorkerProtocolError("WORKER_HANDSHAKE_SCHEMA_INVALID")
        if (
            response.get("protocol") != WORKER_PROTOCOL
            or response.get("type") != "READY"
            or response.get("agent") != agent
            or response.get("worker_id") != worker_id
            or response.get("session_nonce") != session_nonce
        ):
            raise WorkerProtocolError("WORKER_HANDSHAKE_MISMATCH")

    def _validate_task_result(
        self,
        response: dict[str, Any],
        *,
        spec: AgentWorkerSpec,
        worker_id: str,
        session_nonce: str,
        task: AgentTask,
    ) -> tuple[str, str, dict[str, str]]:
        if self._contains_field(response, AUTHORITY_FIELDS):
            raise WorkerProtocolError("WORKER_AUTHORITY_FIELD_FORBIDDEN")
        if set(response) != {
            "protocol",
            "type",
            "agent",
            "worker_id",
            "session_nonce",
            "task_id",
            "correlation_id",
            "status",
            "evidence_ref",
            "result",
        }:
            raise WorkerProtocolError("WORKER_TASK_RESULT_SCHEMA_INVALID")
        if (
            response.get("protocol") != WORKER_PROTOCOL
            or response.get("type") != "TASK_RESULT"
            or response.get("agent") != spec.agent
            or response.get("worker_id") != worker_id
            or response.get("session_nonce") != session_nonce
            or response.get("task_id") != task.task_id
            or response.get("correlation_id") != task.correlation_id
        ):
            raise WorkerProtocolError("WORKER_TASK_CORRELATION_MISMATCH")

        status = response.get("status")
        if not isinstance(status, str) or status not in {
            "COMPLETED",
            "FAILED",
            "BLOCKED",
        }:
            raise WorkerProtocolError("WORKER_TASK_STATUS_INVALID")

        evidence_ref = response.get("evidence_ref", "")
        if not isinstance(evidence_ref, str) or len(evidence_ref) > 512:
            raise WorkerProtocolError("WORKER_EVIDENCE_REFERENCE_INVALID")
        if status == "COMPLETED":
            if not evidence_ref or self.federation.performance_evaluator._resolve_evidence(
                evidence_ref
            ) is None:
                raise WorkerProtocolError("WORKER_EVIDENCE_NOT_VERIFIABLE")
        else:
            evidence_ref = ""

        result = response.get("result", {})
        if not isinstance(result, dict):
            raise WorkerProtocolError("WORKER_RESULT_METADATA_INVALID")
        if set(result) - {"summary", "artifact_type"}:
            raise WorkerProtocolError("WORKER_RESULT_METADATA_INVALID")
        summary = result.get("summary", "")
        artifact_type = result.get("artifact_type", "")
        if (
            not isinstance(summary, str)
            or len(summary) > MAX_SUMMARY_CHARS
            or not isinstance(artifact_type, str)
            or len(artifact_type) > MAX_ARTIFACT_TYPE_CHARS
        ):
            raise WorkerProtocolError("WORKER_RESULT_METADATA_INVALID")

        # Do not persist free-form worker prose or self-assessed quality flags.
        safe_result = {"artifact_type": artifact_type} if artifact_type else {}
        return str(status), evidence_ref, safe_result

    async def _wait_for_task_result(
        self,
        process: asyncio.subprocess.Process,
        *,
        spec: AgentWorkerSpec,
        worker_id: str,
        session_nonce: str,
        task: AgentTask,
    ) -> dict[str, Any]:
        async def keep_claim_alive() -> None:
            cadence = max(0.25, min(10.0, self.federation.lease_seconds / 3.0))
            while True:
                await asyncio.sleep(cadence)
                renewed = await self.federation.renew_task_claim(
                    task.task_id, agent=spec.agent
                )
                if not renewed:
                    raise WorkerProtocolError("WORKER_TASK_CLAIM_LOST")
                await self.federation.heartbeat(
                    spec.agent, worker_id=worker_id, origin="WORKER"
                )

        reader = asyncio.create_task(
            self._read_frame(
                process,
                timeout_seconds=self.response_timeout_seconds,
                max_bytes=MAX_RESULT_BYTES,
                timeout_code="WORKER_TASK_RESPONSE_TIMEOUT",
            )
        )
        keeper = asyncio.create_task(keep_claim_alive())
        try:
            done, _pending = await asyncio.wait(
                {reader, keeper}, return_when=asyncio.FIRST_COMPLETED
            )
            if keeper in done:
                exception = keeper.exception()
                if exception is not None:
                    raise exception
                raise WorkerProtocolError("WORKER_TASK_KEEPALIVE_STOPPED")
            return reader.result()
        finally:
            for pending in (reader, keeper):
                if not pending.done():
                    pending.cancel()
            await asyncio.gather(reader, keeper, return_exceptions=True)

    async def _publish_protocol_error(
        self, spec: AgentWorkerSpec, code: str
    ) -> None:
        await self.federation.publish(
            sender="AURELIA",
            recipients=(spec.agent,),
            message_type="WORKER_PROTOCOL_ERROR",
            payload={
                "agent": spec.agent,
                "worker_runtime": "LOCAL_JSONL_ADAPTER",
                "error_code": code,
                "capital_authority": False,
            },
            correlation_id=f"worker-protocol-error:{spec.agent}:{code}",
            priority=95,
            requires_response=False,
        )

    async def _worker(self, spec: AgentWorkerSpec) -> None:
        restart_delay = max(1.0, self.interval_seconds)
        restart_count = 0
        while self._running:
            process: asyncio.subprocess.Process | None = None
            worker_id = f"agent-worker:{spec.agent}:{secrets.token_hex(12)}"
            session_nonce = secrets.token_urlsafe(24)
            claimed_task_id: str | None = None
            worker_home: str | None = None
            try:
                command = self._command(spec.agent)
                if not command:
                    await self.federation.publish(
                        sender="AURELIA",
                        recipients=(spec.agent,),
                        message_type="CONNECTOR_STATUS",
                        payload={
                            "agent": spec.agent,
                            "worker_runtime": "NOT_CONFIGURED",
                            "provider_session": "NOT_CONFIGURED",
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
                            "reason": "NO_WORKER_COMMAND_CONFIGURED",
                            "capital_authority": False,
                        },
                        correlation_id=f"connector-required:{spec.agent}",
                        priority=95,
                        requires_response=False,
                    )
                    await asyncio.sleep(self.interval_seconds)
                    continue

                worker_home = tempfile.mkdtemp(prefix="aurelia-worker-home-")
                Path(worker_home).chmod(0o700)
                env = self._worker_environment(
                    spec,
                    worker_id=worker_id,
                    session_nonce=session_nonce,
                    home_dir=worker_home,
                )
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=env,
                    limit=MAX_FRAME_BYTES,
                )
                await self._send_frame(
                    process,
                    {
                        "protocol": WORKER_PROTOCOL,
                        "type": "HELLO",
                        "agent": spec.agent,
                        "worker_id": worker_id,
                        "session_nonce": session_nonce,
                    },
                )
                ready = await self._read_frame(
                    process,
                    timeout_seconds=self.handshake_timeout_seconds,
                    max_bytes=4_096,
                    timeout_code="WORKER_HANDSHAKE_TIMEOUT",
                )
                self._validate_handshake(
                    ready,
                    agent=spec.agent,
                    worker_id=worker_id,
                    session_nonce=session_nonce,
                )
                await self.federation.publish(
                    sender="AURELIA",
                    recipients=(spec.agent,),
                    message_type="CONNECTOR_STATUS",
                    payload={
                        "agent": spec.agent,
                        "worker_runtime": "LOCAL_JSONL_ADAPTER",
                        "provider_session": "NOT_ATTESTED_BY_PROTOCOL",
                        "protocol": WORKER_PROTOCOL,
                        "capital_authority": False,
                    },
                    correlation_id=f"connector-status:{spec.agent}:{worker_id}",
                    priority=60,
                    requires_response=False,
                )

                while self._running:
                    if process.returncode is not None:
                        raise WorkerProtocolError("WORKER_PROCESS_EXITED")
                    await self.federation.heartbeat(
                        spec.agent, worker_id=worker_id, origin="WORKER"
                    )
                    task = await self.federation.claim_task(spec.agent)
                    if task is None:
                        await asyncio.sleep(self.interval_seconds)
                        continue

                    claimed_task_id = task.task_id
                    if self._contains_field(task.payload, SENSITIVE_INPUT_FIELDS):
                        await self.federation.complete_task(
                            task.task_id,
                            agent=spec.agent,
                            status="BLOCKED",
                            result={"reason": "WORKER_INPUT_CONTAINS_SENSITIVE_FIELD"},
                        )
                        claimed_task_id = None
                        continue
                    try:
                        json.dumps(task.payload, allow_nan=False)
                    except (TypeError, ValueError):
                        await self.federation.complete_task(
                            task.task_id,
                            agent=spec.agent,
                            status="BLOCKED",
                            result={"reason": "WORKER_INPUT_NOT_JSON_SERIALIZABLE"},
                        )
                        claimed_task_id = None
                        continue

                    await self._send_frame(
                        process,
                        {
                            "protocol": WORKER_PROTOCOL,
                            "type": "TASK",
                            "agent": spec.agent,
                            "worker_id": worker_id,
                            "session_nonce": session_nonce,
                            "task": task.as_payload(),
                        },
                    )
                    try:
                        response = await self._wait_for_task_result(
                            process,
                            spec=spec,
                            worker_id=worker_id,
                            session_nonce=session_nonce,
                            task=task,
                        )
                        status, evidence_ref, safe_result = self._validate_task_result(
                            response,
                            spec=spec,
                            worker_id=worker_id,
                            session_nonce=session_nonce,
                            task=task,
                        )
                        completed = await self.federation.complete_task(
                            task.task_id,
                            agent=spec.agent,
                            status=status,
                            evidence_ref=evidence_ref,
                            result=safe_result,
                        )
                        if not completed:
                            raise WorkerProtocolError("WORKER_TASK_COMPLETION_REJECTED")
                        claimed_task_id = None
                    except WorkerProtocolError as exc:
                        await self.federation.requeue_task(
                            task.task_id,
                            agent=spec.agent,
                            reason=exc.code,
                        )
                        claimed_task_id = None
                        raise

            except asyncio.CancelledError:
                raise
            except WorkerProtocolError as exc:
                await self._publish_protocol_error(spec, exc.code)
            except Exception as exc:
                await self.federation.publish(
                    sender="AURELIA",
                    recipients=(spec.agent,),
                    message_type="WORKER_RUNTIME_ERROR",
                    payload={
                        "agent": spec.agent,
                        "worker_runtime": "LOCAL_JSONL_ADAPTER",
                        "error_class": type(exc).__name__,
                        "capital_authority": False,
                    },
                    correlation_id=f"worker-runtime-error:{spec.agent}:{type(exc).__name__}",
                    priority=95,
                    requires_response=False,
                )
            finally:
                if claimed_task_id is not None:
                    await self.federation.requeue_task(
                        claimed_task_id,
                        agent=spec.agent,
                        reason="WORKER_PROCESS_STOPPED",
                    )
                if process is not None:
                    if process.returncode is None:
                        try:
                            process.terminate()
                        except ProcessLookupError:
                            pass
                        try:
                            await asyncio.wait_for(process.wait(), timeout=5)
                        except asyncio.TimeoutError:
                            try:
                                process.kill()
                            except ProcessLookupError:
                                pass
                            await process.wait()
                    await self.federation.revoke_lease(
                        spec.agent, worker_id=worker_id
                    )
                if worker_home is not None:
                    shutil.rmtree(worker_home, ignore_errors=True)
            if not self._running:
                break
            restart_count += 1
            await asyncio.sleep(
                min(60.0, restart_delay * (2 ** min(restart_count - 1, 6)))
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
