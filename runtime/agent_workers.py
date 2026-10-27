from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from runtime.agent_federation import AgentTask, PersistentAgentFederation

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_MATRIX_PATH = ROOT / "config" / "agent_runtime_provider_matrix.json"
MAX_TASK_REQUEST_BYTES = 1_048_576
MAX_TASK_RESPONSE_BYTES = 1_048_576
SECRET_NAME_PATTERN = re.compile(
    r"(api.?key|access.?token|auth.?token|secret|password|credential|private.?key|bearer)",
    re.IGNORECASE,
)
SENSITIVE_FIELD_PATTERN = SECRET_NAME_PATTERN


@dataclass(frozen=True)
class AgentWorkerSpec:
    agent: str
    command_env: str
    healthcheck_env: str


class AgentWorkerSupervisor:
    """Supervise advisory workers and dispatch tasks through bounded JSON stdio.

    A worker command is a trusted one-task adapter: it reads one JSON request
    from stdin and must write one JSON response to stdout. Its response schema is
    `aurelia.agent_task_response.v1`. It is not a persistent daemon process.

    Liveness is granted only while the supervisor's operator-defined readiness
    command passes. A lease does not independently prove model identity, task
    correctness, or provider authentication. Provider API credentials are
    allowlisted from the canonical provider matrix; unrelated secrets (including
    broker tokens) are deliberately not inherited by an advisory worker process.
    No worker receives capital authority or live-order permission.
    """

    def __init__(
        self,
        federation: PersistentAgentFederation,
        *,
        agents: Iterable[str],
        interval_seconds: float = 10.0,
        healthcheck_timeout_seconds: float = 5.0,
        task_timeout_seconds: float = 120.0,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.federation = federation
        self.environment = dict(os.environ if env is None else env)
        self.agents = tuple(sorted(set(agents)))
        self.interval_seconds = max(0.1, float(interval_seconds))
        self.healthcheck_timeout_seconds = max(0.5, float(healthcheck_timeout_seconds))
        self.task_timeout_seconds = max(0.1, float(task_timeout_seconds))
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._running = False
        try:
            document = json.loads(PROVIDER_MATRIX_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("AGENT_RUNTIME_PROVIDER_MATRIX_UNREADABLE") from exc
        if document.get("schema") != "aurelia.agent_runtime_provider_matrix.v1":
            raise RuntimeError("AGENT_RUNTIME_PROVIDER_MATRIX_SCHEMA_INVALID")
        runtimes = document.get("runtimes")
        if not isinstance(runtimes, list):
            raise RuntimeError("AGENT_RUNTIME_PROVIDER_MATRIX_INVALID")
        self._runtime_specs = {
            str(item["name"]): item for item in runtimes if isinstance(item, dict) and item.get("name")
        }

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
        explicit = self._parse_command(self._env_name(agent))
        if explicit:
            return explicit
        profile = self._runtime_specs.get(agent, {})
        if profile.get("default_adapter_enabled") is True:
            relative = str(profile.get("adapter_script", "")).strip()
            adapter = (ROOT / relative).resolve()
            if relative and adapter.is_file() and ROOT.resolve() in adapter.parents:
                return [sys.executable, str(adapter)]
        return None

    def _healthcheck_command(self, agent: str) -> list[str] | None:
        explicit = self._parse_command(self._healthcheck_env_name(agent))
        if explicit:
            return explicit
        profile = self._runtime_specs.get(agent, {})
        if profile.get("default_adapter_enabled") is True:
            relative = str(profile.get("adapter_script", "")).strip()
            adapter = (ROOT / relative).resolve()
            if relative and adapter.is_file() and ROOT.resolve() in adapter.parents:
                return [sys.executable, str(adapter), "--healthcheck"]
        return None

    @staticmethod
    def _subprocess_identity(agent: str) -> tuple[int | None, int | None]:
        """Run provider CLIs under dedicated non-root UIDs in the production container."""
        if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
            return None, None
        profile = None
        try:
            matrix = json.loads(PROVIDER_MATRIX_PATH.read_text(encoding="utf-8"))
            profile = next(
                item for item in matrix.get("runtimes", [])
                if isinstance(item, dict) and item.get("name") == agent
            )
        except (OSError, ValueError, StopIteration, json.JSONDecodeError):
            profile = None
        if not isinstance(profile, dict):
            raise ValueError("AGENT_SANDBOX_PROFILE_MISSING")
        uid = profile.get("sandbox_uid")
        gid = profile.get("sandbox_gid")
        if isinstance(uid, bool) or not isinstance(uid, int) or uid <= 0:
            raise ValueError("AGENT_SANDBOX_UID_REQUIRED")
        if isinstance(gid, bool) or not isinstance(gid, int) or gid <= 0:
            raise ValueError("AGENT_SANDBOX_GID_REQUIRED")
        try:
            import grp
            import pwd
            account = pwd.getpwuid(uid)
            group = grp.getgrgid(gid)
        except (ImportError, KeyError) as exc:
            raise ValueError("AGENT_SANDBOX_ACCOUNT_MISSING") from exc
        if account.pw_gid != gid or not account.pw_name.startswith("aurelia-agent-"):
            raise ValueError("AGENT_SANDBOX_ACCOUNT_MISMATCH")
        if group.gr_name != account.pw_name:
            raise ValueError("AGENT_SANDBOX_GROUP_MISMATCH")
        return uid, gid

    def _worker_environment(
        self,
        agent: str,
        *,
        worker_id: str,
        task_id: str = "",
        healthcheck_only: bool = False,
    ) -> dict[str, str]:
        """Build a minimal worker environment; never copy arbitrary parent secrets."""
        spec = self._runtime_specs.get(agent, {})
        credential_names: set[str] = set()
        pass_list = spec.get("credential_env_pass_list", [])
        if isinstance(pass_list, list):
            credential_names.update(str(item) for item in pass_list)
        provider_mapping = spec.get("credential_env_by_provider")
        provider_env = str(spec.get("provider_env", "")).strip()
        if isinstance(provider_mapping, dict):
            provider = str(self.environment.get(provider_env, "")).strip().lower()
            selected_names = provider_mapping.get(provider, [])
            if isinstance(selected_names, list):
                credential_names.update(str(item) for item in selected_names)
        elif not credential_names:
            # Legacy custom profiles receive at most one configured provider key,
            # never every candidate credential in credential_env_any.
            for candidate in spec.get("credential_env_any", []):
                if str(self.environment.get(str(candidate), "")).strip():
                    credential_names.add(str(candidate))
                    break
        extra_names = {
            str(item) for item in spec.get("runtime_env_allowlist", [])
        }
        base_names = {
            "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM", "NO_COLOR",
            "SYSTEMROOT", "WINDIR",
        }
        child_env = {
            name: str(self.environment[name])
            for name in base_names | credential_names | extra_names
            if name in self.environment and str(self.environment[name]).strip()
        }

        home_root = Path(
            str(self.environment.get(
                "AURELIA_WORKER_HOME_ROOT",
                self.federation.lease_path.parent / "agent-homes",
            ))
        ).expanduser()
        if not home_root.is_absolute():
            raise ValueError("AURELIA_WORKER_HOME_ROOT_MUST_BE_ABSOLUTE")
        home_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if home_root.is_symlink():
            raise ValueError("AURELIA_WORKER_HOME_ROOT_MUST_NOT_BE_SYMLINK")
        os.chmod(home_root, 0o711 if os.geteuid() == 0 else 0o700)
        safe_agent = "".join(c.lower() if c.isalnum() else "-" for c in agent).strip("-")
        if not safe_agent:
            raise ValueError("AGENT_NAME_INVALID_FOR_WORKER_HOME")
        home = home_root / safe_agent
        if home.is_symlink():
            raise ValueError("AGENT_WORKER_HOME_MUST_NOT_BE_SYMLINK")
        home.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(home, 0o700)
        sandbox_uid, sandbox_gid = self._subprocess_identity(agent)
        if sandbox_uid is not None and sandbox_gid is not None:
            os.chown(home, sandbox_uid, sandbox_gid)
        temporary = home / "tmp"
        temporary.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(temporary, 0o700)
        if sandbox_uid is not None and sandbox_gid is not None:
            os.chown(temporary, sandbox_uid, sandbox_gid)

        child_env.update({
            "HOME": str(home),
            "TMPDIR": str(temporary),
            "TMP": str(temporary),
            "TEMP": str(temporary),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "AURELIA_AGENT_ID": agent,
            "AURELIA_AGENT_WORKER_ID": worker_id,
            "AURELIA_AGENT_WORKER_PROTOCOL": "STDIO_JSON_TASK_V1",
            "AURELIA_AGENT_HEALTHCHECK_ONLY": "true" if healthcheck_only else "false",
        })
        if task_id:
            child_env["AURELIA_AGENT_TASK_ID"] = task_id
        return child_env

    def _known_secret_values(self) -> tuple[str, ...]:
        values = {
            str(value)
            for name, value in self.environment.items()
            if SECRET_NAME_PATTERN.search(str(name))
            and isinstance(value, str)
            and len(value) >= 6
        }
        return tuple(sorted(values, key=len, reverse=True))

    def _redact(self, value: Any) -> Any:
        secrets = self._known_secret_values()
        if isinstance(value, dict):
            output: dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                if SENSITIVE_FIELD_PATTERN.search(key_text) and item not in (None, "", [], {}):
                    output[key_text] = "[REDACTED]"
                else:
                    output[key_text] = self._redact(item)
            return output
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        if isinstance(value, tuple):
            return [self._redact(item) for item in value]
        if isinstance(value, str):
            result = value
            for secret in secrets:
                result = result.replace(secret, "[REDACTED]")
            return result
        return value

    async def _run_healthcheck(
        self, command: list[str], *, env: dict[str, str], timeout_seconds: float | None = None
    ) -> bool:
        """Run a bounded, output-suppressed provider readiness command."""
        process = None
        timeout = self.healthcheck_timeout_seconds if timeout_seconds is None else max(0.5, float(timeout_seconds))
        try:
            uid, gid = self._subprocess_identity(env.get("AURELIA_AGENT_ID", ""))
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
                cwd=env.get("HOME"),
                user=uid,
                group=gid,
                extra_groups=() if uid is not None else None,
            )
            return_code = await asyncio.wait_for(
                process.wait(), timeout=timeout
            )
            return return_code == 0
        except asyncio.CancelledError:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            raise
        except (OSError, ValueError, asyncio.TimeoutError):
            if process is not None and process.returncode is None:
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

    async def _read_bounded_stdout(self, reader: asyncio.StreamReader) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await reader.read(min(65536, MAX_TASK_RESPONSE_BYTES + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_TASK_RESPONSE_BYTES:
                raise ValueError("WORKER_RESPONSE_TOO_LARGE")
            chunks.append(chunk)
        return b"".join(chunks)

    async def _execute_task(
        self,
        command: list[str],
        task: AgentTask,
        *,
        agent: str,
        env: dict[str, str],
    ) -> dict[str, Any]:
        """Run a one-shot JSON adapter; never expose unrelated runtime secrets."""
        request = {
            "schema": "aurelia.agent_task_request.v1",
            "protocol": "STDIO_JSON_TASK_V1",
            "agent": agent,
            "task": self._redact(task.as_payload()),
            "policy": {
                "capital_authority": False,
                "live_order_submission": False,
                "live_lock_mutation": False,
                "broker_credentials_are_not_provided": True,
                "response_schema": "aurelia.agent_task_response.v1",
            },
        }
        encoded = json.dumps(request, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if len(encoded) > MAX_TASK_REQUEST_BYTES:
            return {
                "status": "FAILED",
                "result": {"error_code": "WORKER_REQUEST_TOO_LARGE", "task_id": task.task_id},
                "evidence_ref": "",
            }
        process = None
        stdout_task: asyncio.Task[bytes] | None = None
        wait_task: asyncio.Task[int] | None = None
        try:
            uid, gid = self._subprocess_identity(agent)
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
                cwd=env.get("HOME"),
                user=uid,
                group=gid,
                extra_groups=() if uid is not None else None,
            )
            assert process.stdin is not None and process.stdout is not None
            stdout_task = asyncio.create_task(self._read_bounded_stdout(process.stdout))
            wait_task = asyncio.create_task(process.wait())
            process.stdin.write(encoded + b"\n")
            await process.stdin.drain()
            process.stdin.close()
            stdout, return_code = await asyncio.wait_for(
                asyncio.gather(stdout_task, wait_task),
                timeout=self.task_timeout_seconds,
            )
        except asyncio.CancelledError:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            pending = [item for item in (stdout_task, wait_task) if item is not None and not item.done()]
            for item in pending:
                item.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            raise
        except asyncio.TimeoutError:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            if stdout_task is not None:
                stdout_task.cancel()
            if wait_task is not None:
                wait_task.cancel()
            pending = [item for item in (stdout_task, wait_task) if item is not None and not item.done()]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            return {
                "status": "FAILED",
                "result": {"error_code": "WORKER_COMMAND_TIMEOUT", "task_id": task.task_id},
                "evidence_ref": "",
            }
        except ValueError as exc:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            if stdout_task is not None:
                stdout_task.cancel()
            if wait_task is not None:
                wait_task.cancel()
            pending = [item for item in (stdout_task, wait_task) if item is not None and not item.done()]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            error_code = str(exc) if str(exc) == "WORKER_RESPONSE_TOO_LARGE" else "WORKER_REQUEST_WRITE_FAILED"
            return {
                "status": "FAILED",
                "result": {"error_code": error_code, "task_id": task.task_id},
                "evidence_ref": "",
            }
        except (OSError, RuntimeError):
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            if stdout_task is not None:
                stdout_task.cancel()
            if wait_task is not None:
                wait_task.cancel()
            pending = [item for item in (stdout_task, wait_task) if item is not None and not item.done()]
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            return {
                "status": "FAILED",
                "result": {"error_code": "WORKER_COMMAND_START_OR_IO_FAILED", "task_id": task.task_id},
                "evidence_ref": "",
            }

        if return_code != 0:
            return {
                "status": "FAILED",
                "result": {
                    "error_code": "WORKER_COMMAND_EXITED_NONZERO",
                    "return_code": int(return_code),
                    "task_id": task.task_id,
                },
                "evidence_ref": "",
            }
        try:
            response = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            response = None
        if not isinstance(response, dict):
            return {
                "status": "FAILED",
                "result": {"error_code": "WORKER_RESPONSE_INVALID_JSON", "task_id": task.task_id},
                "evidence_ref": "",
            }
        if (
            response.get("schema") != "aurelia.agent_task_response.v1"
            or response.get("task_id") != task.task_id
            or response.get("status") not in {"COMPLETED", "FAILED", "BLOCKED"}
            or not isinstance(response.get("result", {}), dict)
        ):
            return {
                "status": "FAILED",
                "result": {"error_code": "WORKER_RESPONSE_SCHEMA_INVALID", "task_id": task.task_id},
                "evidence_ref": "",
            }
        evidence_ref = response.get("evidence_ref", "")
        if not isinstance(evidence_ref, str):
            evidence_ref = ""
        return {
            "status": str(response["status"]),
            "result": self._redact(response.get("result", {})),
            "evidence_ref": self._redact(evidence_ref),
        }

    async def _publish_task_result(
        self,
        *,
        agent: str,
        task: AgentTask,
        outcome: dict[str, Any],
    ) -> None:
        status = str(outcome.get("status", "FAILED"))
        result = outcome.get("result", {})
        if not isinstance(result, dict):
            status = "FAILED"
            result = {"error_code": "WORKER_RESULT_INVALID", "task_id": task.task_id}
        evidence_ref = outcome.get("evidence_ref", "")
        if not isinstance(evidence_ref, str):
            evidence_ref = ""
        completed = await self.federation.complete_task(
            task.task_id,
            agent=agent,
            status=status,
            evidence_ref=evidence_ref,
            result=result,
        )
        if completed:
            await self.federation.publish(
                sender="AURELIA",
                recipients=(agent,),
                message_type="WORKER_ACK",
                payload={
                    "agent": agent,
                    "task_id": task.task_id,
                    "status": status,
                    "evidence_ref": evidence_ref,
                    "capital_authority": False,
                    "secret_values_emitted": False,
                },
                correlation_id=f"worker-ack:{task.task_id}",
                priority=task.priority,
                requires_response=False,
            )
        else:
            await self.federation.publish(
                sender="AURELIA",
                recipients=(agent,),
                message_type="WORKER_ACK_REJECTED",
                payload={
                    "agent": agent,
                    "task_id": task.task_id,
                    "reason": "TASK_STATE_OR_OWNERSHIP_CHANGED",
                    "capital_authority": False,
                },
                correlation_id=f"worker-ack-rejected:{task.task_id}",
                priority=95,
                requires_response=False,
            )

    async def _worker(self, spec: AgentWorkerSpec) -> None:
        worker_id_base = f"agent-worker:{spec.agent}:{os.getpid()}"
        restart_delay = max(1.0, self.interval_seconds)
        restart_count = 0

        while self._running:
            command_raw = str(self.environment.get(spec.command_env, "")).strip()
            healthcheck_raw = str(self.environment.get(spec.healthcheck_env, "")).strip()
            command = self._command(spec.agent)
            healthcheck = self._healthcheck_command(spec.agent)
            profile = self._runtime_specs.get(spec.agent, {})
            built_in_adapter = not command_raw and profile.get("default_adapter_enabled") is True
            if command is None:
                reason = "WORKER_COMMAND_INVALID" if command_raw else "WORKER_COMMAND_MISSING"
                await self._publish_connector_required(spec.agent, reason)
                try:
                    await asyncio.sleep(restart_delay)
                except asyncio.CancelledError:
                    raise
                continue
            if healthcheck is None:
                reason = (
                    "WORKER_HEALTHCHECK_COMMAND_INVALID"
                    if healthcheck_raw else "WORKER_HEALTHCHECK_COMMAND_MISSING"
                )
                await self._publish_connector_required(spec.agent, reason)
                try:
                    await asyncio.sleep(restart_delay)
                except asyncio.CancelledError:
                    raise
                continue

            healthcheck_interval = (
                max(1.0, float(profile.get("healthcheck_interval_seconds", 300)))
                if built_in_adapter else self.interval_seconds
            )
            healthcheck_timeout = (
                max(0.5, float(profile.get("healthcheck_timeout_seconds", 55)))
                if built_in_adapter else self.healthcheck_timeout_seconds
            )
            worker_id = f"{worker_id_base}:r{restart_count}"
            status_published = False
            in_flight_task: AgentTask | None = None
            task_runner: asyncio.Task[dict[str, Any]] | None = None
            last_healthcheck_at = 0.0
            try:
                while self._running:
                    now = asyncio.get_running_loop().time()
                    if last_healthcheck_at == 0.0 or now - last_healthcheck_at >= healthcheck_interval:
                        health_env = self._worker_environment(
                            spec.agent, worker_id=worker_id, healthcheck_only=True
                        )
                        healthy = await self._run_healthcheck(
                            healthcheck, env=health_env, timeout_seconds=healthcheck_timeout
                        )
                        if not healthy:
                            if in_flight_task is not None and task_runner is not None:
                                task_runner.cancel()
                                try:
                                    await task_runner
                                except (asyncio.CancelledError, Exception):
                                    pass
                                await self._publish_task_result(
                                    agent=spec.agent,
                                    task=in_flight_task,
                                    outcome={
                                        "status": "BLOCKED",
                                        "result": {
                                            "error_code": "WORKER_HEALTHCHECK_FAILED_DURING_TASK",
                                            "task_id": in_flight_task.task_id,
                                        },
                                    },
                                )
                                in_flight_task = None
                                task_runner = None
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
                        last_healthcheck_at = asyncio.get_running_loop().time()

                    if not status_published:
                        await self.federation.publish(
                            sender="AURELIA",
                            recipients=(spec.agent,),
                            message_type="CONNECTOR_STATUS",
                            payload={
                                "agent": spec.agent,
                                "worker_runtime": "SUPERVISED_ONE_SHOT_ADAPTER",
                                "worker_process_status": "READY_FOR_TASK_DISPATCH",
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

                    await self.federation.heartbeat(
                        spec.agent, worker_id=worker_id, origin="WORKER"
                    )

                    if task_runner is not None and task_runner.done() and in_flight_task is not None:
                        try:
                            outcome = task_runner.result()
                        except asyncio.CancelledError:
                            outcome = {
                                "status": "BLOCKED",
                                "result": {
                                    "error_code": "WORKER_TASK_CANCELLED",
                                    "task_id": in_flight_task.task_id,
                                },
                            }
                        except Exception as exc:
                            outcome = {
                                "status": "FAILED",
                                "result": {
                                    "error_code": "WORKER_ADAPTER_EXCEPTION",
                                    "error_class": type(exc).__name__,
                                    "task_id": in_flight_task.task_id,
                                },
                            }
                        await self._publish_task_result(
                            agent=spec.agent, task=in_flight_task, outcome=outcome
                        )
                        in_flight_task = None
                        task_runner = None

                    if task_runner is None:
                        task = await self.federation.claim_task(spec.agent)
                        if task is not None:
                            await self.federation.publish(
                                sender="AURELIA",
                                recipients=(spec.agent,),
                                message_type="AGENT_TASK_CLAIMED",
                                payload={
                                    "task_id": task.task_id,
                                    "task_type": task.task_type,
                                    "payload": self._redact(task.payload),
                                    "worker_protocol": "STDIO_JSON_TASK_V1",
                                    "capital_authority": False,
                                    "secret_values_emitted": False,
                                },
                                correlation_id=task.correlation_id,
                                priority=task.priority,
                                requires_response=True,
                            )
                            task_env = self._worker_environment(
                                spec.agent, worker_id=worker_id, task_id=task.task_id
                            )
                            in_flight_task = task
                            task_runner = asyncio.create_task(
                                self._execute_task(
                                    command, task, agent=spec.agent, env=task_env
                                ),
                                name=f"agent-task:{spec.agent}:{task.task_id[:12]}",
                            )
                    try:
                        await asyncio.sleep(self.interval_seconds)
                    except asyncio.CancelledError:
                        raise
            except asyncio.CancelledError:
                if task_runner is not None and not task_runner.done():
                    task_runner.cancel()
                    try:
                        await task_runner
                    except asyncio.CancelledError:
                        pass
                # Leave an interrupted task CLAIMED. The normal stale-claim
                # recovery path will requeue it after its lease/claim timeout.
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
                        "worker_runtime": "SUPERVISED_ONE_SHOT_ADAPTER",
                        "error_class": type(exc).__name__,
                        "restart_policy": "ALWAYS_WHILE_RUNTIME_HEALTHY",
                        "capital_authority": False,
                        "secret_values_emitted": False,
                    },
                    correlation_id=f"worker-error:{spec.agent}:{restart_count}",
                    priority=95,
                    requires_response=False,
                )
                if task_runner is not None and not task_runner.done():
                    task_runner.cancel()
                    try:
                        await task_runner
                    except asyncio.CancelledError:
                        pass

            if not self._running:
                break
            restart_count += 1
            if built_in_adapter:
                restart_delay = min(
                    300.0,
                    max(60.0, self.interval_seconds) * (2 ** min(restart_count, 3)),
                )
            else:
                restart_delay = max(1.0, self.interval_seconds)
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
