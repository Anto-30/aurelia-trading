from __future__ import annotations

import asyncio
import inspect
import os
import socket
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from runtime.agent_federation import AgentTask, PersistentAgentFederation

WorkerHandler = Callable[[AgentTask], Awaitable[dict[str, Any]] | dict[str, Any]]


@dataclass(frozen=True)
class WorkerStatus:
    agent: str
    worker_id: str
    state: str
    last_error: str | None = None


class SupervisedAgentWorker:
    """A real worker lane with worker-owned liveness and durable task recovery.

    The lane only becomes ACTIVE after a handler is configured and the worker
    successfully starts. A configured roster entry without a provider/handler
    remains UNAVAILABLE; no synthetic heartbeat is emitted.
    """

    VALID_STATES = {
        "STARTING",
        "ACTIVE",
        "WAITING_FOR_EVENT",
        "DEGRADED",
        "FAILED",
        "STOPPED",
        "UNAVAILABLE",
    }

    def __init__(
        self,
        federation: PersistentAgentFederation,
        *,
        agent: str,
        handler: WorkerHandler | None,
        poll_seconds: float = 2.0,
        worker_id: str | None = None,
    ) -> None:
        self.federation = federation
        self.agent = agent
        self.handler = handler
        self.poll_seconds = max(0.1, float(poll_seconds))
        self.worker_id = worker_id or (
            f"{agent}:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"
        )
        self._task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._state = "STOPPED"
        self._last_error: str | None = None

    @property
    def status(self) -> WorkerStatus:
        return WorkerStatus(self.agent, self.worker_id, self._state, self._last_error)

    async def _heartbeat(self) -> None:
        interval = max(0.1, min(self.federation.lease_seconds / 3.0, 15.0))
        while not self._stop.is_set():
            await self.federation.heartbeat(
                self.agent, worker_id=self.worker_id, origin="WORKER"
            )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def _run(self) -> None:
        while not self._stop.is_set():
            recovered = await self.federation.recover_stale_tasks()
            if recovered:
                await self.federation.publish(
                    sender=self.agent,
                    recipients=("AURELIA",),
                    message_type="WORKER_RECOVERY",
                    payload={
                        "worker_id": self.worker_id,
                        "recovered_tasks": list(recovered),
                        "capital_authority": False,
                    },
                    correlation_id=f"worker-recovery:{self.worker_id}",
                    priority=85,
                )

            task = await self.federation.claim_task(self.agent)
            if task is None:
                self._state = "WAITING_FOR_EVENT"
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.poll_seconds)
                except asyncio.TimeoutError:
                    continue
                continue

            self._state = "ACTIVE"
            await self.federation.publish(
                sender=self.agent,
                recipients=("AURELIA",),
                message_type="WORKER_PROGRESS",
                payload={
                    "worker_id": self.worker_id,
                    "task_id": task.task_id,
                    "state": "RUNNING",
                    "capital_authority": False,
                },
                correlation_id=task.correlation_id,
                priority=60,
            )
            try:
                result = self.handler(task) if self.handler else {}
                if inspect.isawaitable(result):
                    result = await result
                if not isinstance(result, dict):
                    result = {"result": result}
                await self.federation.complete_task(
                    task.task_id, agent=self.agent, status="COMPLETED"
                )
                await self.federation.publish(
                    sender=self.agent,
                    recipients=("AURELIA",),
                    message_type="WORKER_ACK",
                    payload={
                        "worker_id": self.worker_id,
                        "task_id": task.task_id,
                        "state": "COMPLETED",
                        "result": result,
                        "capital_authority": False,
                    },
                    correlation_id=task.correlation_id,
                    priority=70,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                self._state = "DEGRADED"
                await self.federation.complete_task(
                    task.task_id, agent=self.agent, status="FAILED"
                )
                await self.federation.publish(
                    sender=self.agent,
                    recipients=("AURELIA",),
                    message_type="WORKER_FAILURE",
                    payload={
                        "worker_id": self.worker_id,
                        "task_id": task.task_id,
                        "state": "FAILED",
                        "error": self._last_error,
                        "capital_authority": False,
                    },
                    correlation_id=task.correlation_id,
                    priority=95,
                )

    async def start(self) -> WorkerStatus:
        if self._task and not self._task.done():
            return self.status
        if self.handler is None:
            self._state = "UNAVAILABLE"
            return self.status

        self._stop.clear()
        self._state = "STARTING"
        self._last_error = None
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat(), name=f"worker-heartbeat:{self.worker_id}"
        )
        # Establish the first worker-owned lease before reporting ACTIVE.
        await federation_heartbeat = self.federation.heartbeat(
            self.agent, worker_id=self.worker_id, origin="WORKER"
        )
        del await federation_heartbeat
        self._state = "ACTIVE"
        self._task = asyncio.create_task(
            self._run(), name=f"agent-worker:{self.agent}:{self.worker_id}"
        )
        return self.status

    async def stop(self) -> WorkerStatus:
        self._stop.set()
        for task in (self._task, self._heartbeat_task):
            if task is not None:
                task.cancel()
        for task in (self._task, self._heartbeat_task):
            if task is not None:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._task = None
        self._heartbeat_task = None
        self._state = "STOPPED"
        return self.status
