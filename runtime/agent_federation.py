from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from runtime.core.events import event_envelope, sha256
from runtime.core.journal import AppendOnlyJournal


@dataclass(frozen=True)
class AgentMessage:
    message_id: str
    sender: str
    recipients: tuple[str, ...]
    message_type: str
    payload: dict[str, Any]
    created_at: datetime
    correlation_id: str
    priority: int = 50
    requires_response: bool = False

    def as_payload(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "recipients": self.recipients,
            "message_type": self.message_type,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "priority": self.priority,
            "requires_response": self.requires_response,
        }


@dataclass(frozen=True)
class AgentLease:
    agent: str
    lease_id: str
    worker_id: str
    origin: str
    heartbeat_at: datetime
    expires_at: datetime

    @property
    def active(self) -> bool:
        return datetime.now(timezone.utc) < self.expires_at


@dataclass(frozen=True)
class AgentTask:
    task_id: str
    task_type: str
    priority: int
    assigned_agent: str | None
    payload: dict[str, Any]
    created_at: datetime
    correlation_id: str
    status: str = "PENDING"
    claimed_at: datetime | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "priority": self.priority,
            "assigned_agent": self.assigned_agent,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "status": self.status,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
        }


class PersistentAgentFederation:
    """Durable advisory/engineering message bus for the registered agents.

    The federation never grants capital authority. It persists messages and
    leases so worker restarts do not erase context or acknowledgements.
    """

    def __init__(
        self,
        *,
        journal_path: str | Path,
        lease_path: str | Path,
        config_hash: str,
        source_hash: str,
        lease_seconds: float = 45.0,
        task_path: str | Path | None = None,
    ) -> None:
        self.journal = AppendOnlyJournal(journal_path)
        self.lease_path = Path(lease_path)
        self.lease_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_hash = config_hash
        self.source_hash = source_hash
        self.lease_seconds = max(5.0, lease_seconds)
        self._lock = asyncio.Lock()
        self._seen_messages_path = self.lease_path.with_name("federation-seen-messages.json")
        self.task_path = Path(task_path) if task_path is not None else self.lease_path.with_name("federation-tasks.json")
        self.task_path.parent.mkdir(parents=True, exist_ok=True)
        self._stale_notified: set[str] = set()

    def _append(self, event_type: str, payload: dict[str, Any], correlation_id: str) -> None:
        event_id = f"{event_type}:{sha256({ 'payload': payload, 'correlation_id': correlation_id })[:20]}"
        self.journal.append(
            event_envelope(
                event_type=event_type,
                event_id=event_id,
                correlation_id=correlation_id,
                payload=payload,
                source_hash=self.source_hash,
                config_hash=self.config_hash,
            )
        )

    def _load_leases(self) -> dict[str, dict[str, str]]:
        if not self.lease_path.exists():
            return {}
        try:
            payload = json.loads(self.lease_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return {}
        return dict(payload.get("leases", {})) if isinstance(payload, dict) else {}

    def _load_seen_messages(self) -> set[str]:
        if not self._seen_messages_path.exists():
            return set()
        try:
            payload = json.loads(self._seen_messages_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return set()
        values = payload.get("message_ids", []) if isinstance(payload, dict) else []
        return {str(value) for value in values}

    def _save_seen_messages(self, message_ids: set[str]) -> None:
        temp = self._seen_messages_path.with_suffix(".tmp")
        temp.write_text(json.dumps({"version": 1, "message_ids": sorted(message_ids)}, sort_keys=True), encoding="utf-8")
        temp.replace(self._seen_messages_path)

    def _save_leases(self, leases: dict[str, dict[str, str]]) -> None:
        temp = self.lease_path.with_suffix(self.lease_path.suffix + ".tmp")
        temp.write_text(json.dumps({"version": 1, "leases": leases}, sort_keys=True), encoding="utf-8")
        temp.replace(self.lease_path)



    def _load_tasks(self) -> list[dict[str, Any]]:
        if not self.task_path.exists():
            return []
        try:
            payload = json.loads(self.task_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return []
        values = payload.get("tasks", []) if isinstance(payload, dict) else []
        return [dict(value) for value in values if isinstance(value, dict)]

    def _save_tasks(self, tasks: list[dict[str, Any]]) -> None:
        temp = self.task_path.with_suffix(self.task_path.suffix + ".tmp")
        temp.write_text(json.dumps({"version": 1, "tasks": tasks}, sort_keys=True), encoding="utf-8")
        temp.replace(self.task_path)

    def stale_agents(self) -> tuple[str, ...]:
        leases = self._load_leases()
        now = datetime.now(timezone.utc)
        return tuple(sorted(
            agent for agent, value in leases.items()
            if datetime.fromisoformat(value["expires_at"]) <= now
        ))

    async def enqueue_task(
        self,
        *,
        task_type: str,
        payload: dict[str, Any],
        correlation_id: str,
        priority: int = 50,
        assigned_agent: str | None = None,
    ) -> AgentTask:
        task_id = f"task:{sha256({'task_type': task_type, 'payload': payload, 'correlation_id': correlation_id, 'assigned_agent': assigned_agent})}"
        task = AgentTask(
            task_id=task_id,
            task_type=task_type,
            priority=max(0, min(100, int(priority))),
            assigned_agent=assigned_agent,
            payload=payload,
            created_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
        )
        async with self._lock:
            tasks = self._load_tasks()
            existing = next((x for x in tasks if x.get("task_id") == task_id), None)
            if existing:
                return AgentTask(**{
                    "task_id": existing["task_id"],
                    "task_type": existing["task_type"],
                    "priority": int(existing.get("priority", 50)),
                    "assigned_agent": existing.get("assigned_agent"),
                    "payload": existing.get("payload", {}),
                    "created_at": datetime.fromisoformat(existing["created_at"]),
                    "correlation_id": existing["correlation_id"],
                    "status": existing.get("status", "PENDING"),
                })
            tasks.append(task.as_payload())
            self._save_tasks(tasks)
        self._append("AGENT_TASK_ENQUEUED", task.as_payload(), task.correlation_id)
        return task

    async def claim_task(self, agent: str) -> AgentTask | None:
        async with self._lock:
            tasks = self._load_tasks()
            candidates = [
                x for x in tasks
                if x.get("status") == "PENDING"
                and (x.get("assigned_agent") in (None, agent))
            ]
            if not candidates:
                return None
            candidates.sort(key=lambda x: (-int(x.get("priority", 50)), x.get("created_at", "")))
            selected = candidates[0]
            selected["status"] = "CLAIMED"
            selected["assigned_agent"] = agent
            selected["claimed_at"] = datetime.now(timezone.utc).isoformat()
            self._save_tasks(tasks)
        self._append("AGENT_TASK_CLAIMED", selected, selected["correlation_id"])
        return AgentTask(
            task_id=selected["task_id"],
            task_type=selected["task_type"],
            priority=int(selected.get("priority", 50)),
            assigned_agent=selected.get("assigned_agent"),
            payload=selected.get("payload", {}),
            created_at=datetime.fromisoformat(selected["created_at"]),
            correlation_id=selected["correlation_id"],
            status="CLAIMED",
            claimed_at=(
                datetime.fromisoformat(selected["claimed_at"])
                if selected.get("claimed_at")
                else None
            ),
        )

    async def complete_task(self, task_id: str, *, agent: str, status: str = "COMPLETED") -> bool:
        if status not in {"COMPLETED", "FAILED", "BLOCKED"}:
            raise ValueError("INVALID_TASK_STATUS")
        async with self._lock:
            tasks = self._load_tasks()
            selected = next((x for x in tasks if x.get("task_id") == task_id), None)
            if selected is None or selected.get("assigned_agent") != agent or selected.get("status") != "CLAIMED":
                return False
            selected["status"] = status
            self._save_tasks(tasks)
        self._append("AGENT_TASK_COMPLETED", {"task_id": task_id, "agent": agent, "status": status}, task_id)
        return True

    async def recover_stale_tasks(self) -> tuple[str, ...]:
        now = datetime.now(timezone.utc)
        recovered: list[str] = []
        async with self._lock:
            tasks = self._load_tasks()
            changed = False
            for task in tasks:
                if task.get("status") != "CLAIMED" or not task.get("claimed_at"):
                    continue
                try:
                    claimed_at = datetime.fromisoformat(str(task["claimed_at"]))
                except (TypeError, ValueError):
                    continue
                if now - claimed_at <= timedelta(seconds=self.lease_seconds):
                    continue
                task["status"] = "PENDING"
                task["assigned_agent"] = None
                task.pop("claimed_at", None)
                recovered.append(str(task.get("task_id")))
                changed = True
            if changed:
                self._save_tasks(tasks)
        for task_id in recovered:
            self._append(
                "AGENT_TASK_REQUEUED",
                {"task_id": task_id, "reason": "CLAIM_LEASE_EXPIRED"},
                task_id,
            )
        return tuple(recovered)

    def pending_tasks(self, agent: str | None = None) -> list[dict[str, Any]]:
        rows = [
            x for x in self._load_tasks()
            if x.get("status") == "PENDING"
            and (agent is None or x.get("assigned_agent") in (None, agent))
        ]
        rows.sort(key=lambda x: (-int(x.get("priority", 50)), x.get("created_at", "")))
        return rows

    async def heartbeat(
        self,
        agent: str,
        *,
        worker_id: str | None = None,
        origin: str = "WORKER",
    ) -> AgentLease:
        if origin not in {"WORKER", "TEST"}:
            raise PermissionError("AGENT_HEARTBEAT_ORIGIN_FORBIDDEN")
        if not worker_id or not str(worker_id).strip():
            raise ValueError("WORKER_ID_REQUIRED")
        worker_id = str(worker_id).strip()
        now = datetime.now(timezone.utc)
        lease = AgentLease(
            agent=agent,
            lease_id=f"lease:{agent}:{worker_id}:{int(now.timestamp() * 1000)}",
            worker_id=worker_id,
            origin=origin,
            heartbeat_at=now,
            expires_at=now + timedelta(seconds=self.lease_seconds),
        )
        async with self._lock:
            leases = self._load_leases()
            leases[agent] = {
                "lease_id": lease.lease_id,
                "worker_id": lease.worker_id,
                "origin": lease.origin,
                "heartbeat_at": lease.heartbeat_at.isoformat(),
                "expires_at": lease.expires_at.isoformat(),
            }
            self._save_leases(leases)
        self._append(
            "AGENT_HEARTBEAT",
            {
                "agent": agent,
                "worker_id": worker_id,
                "origin": origin,
                "lease_id": lease.lease_id,
                "expires_at": lease.expires_at.isoformat(),
            },
            correlation_id=f"agent:{agent}:worker:{worker_id}",
        )
        return lease

    async def register_agents(self, agents: Iterable[str]) -> None:
        """Register the configured roster without creating a liveness lease.

        Role/catalog registration is not a heartbeat. Only a real worker (or
        an explicitly marked test) may create/renew an agent lease.
        """
        roster = tuple(sorted(set(str(agent) for agent in agents if str(agent).strip())))
        if not roster:
            return
        self._append(
            "AGENT_ROSTER_REGISTERED",
            {
                "agents": roster,
                "synthetic_heartbeat": False,
            },
            correlation_id=f"agent-roster:{sha256(roster)[:20]}",
        )

    def active_agents(self) -> tuple[str, ...]:
        leases = self._load_leases()
        now = datetime.now(timezone.utc)
        active: list[str] = []
        for agent, value in leases.items():
            worker_id = str(value.get("worker_id", "")).strip()
            origin = str(value.get("origin", ""))
            expires_at = value.get("expires_at")
            if not worker_id or origin not in {"WORKER", "TEST"} or not expires_at:
                continue
            try:
                if datetime.fromisoformat(str(expires_at)) > now:
                    active.append(agent)
            except (TypeError, ValueError):
                continue
        return tuple(sorted(active))

    async def publish(
        self,
        *,
        sender: str,
        recipients: Iterable[str],
        message_type: str,
        payload: dict[str, Any],
        correlation_id: str,
        priority: int = 50,
        requires_response: bool = False,
    ) -> AgentMessage:
        now = datetime.now(timezone.utc)
        recipients_tuple = tuple(sorted(set(recipients)))
        if sender != "AURELIA" and any(
            payload.get(key) is True
            for key in (
                "capital_authority",
                "final_execution_authorization",
                "live_trading_enabled",
                "order_submission_permitted",
            )
        ):
            raise PermissionError("EXTERNAL_AGENT_CAPITAL_AUTHORITY_FORBIDDEN")
        message = AgentMessage(
            message_id=f"msg:{sha256({'sender': sender, 'recipients': recipients_tuple, 'message_type': message_type, 'payload': payload, 'correlation_id': correlation_id})}",
            sender=sender,
            recipients=recipients_tuple,
            message_type=message_type,
            payload=payload,
            created_at=now,
            correlation_id=correlation_id,
            priority=max(0, min(100, int(priority))),
            requires_response=requires_response,
        )
        async with self._lock:
            seen = self._load_seen_messages()
            if message.message_id in seen:
                return message
            seen.add(message.message_id)
            self._save_seen_messages(seen)
            self._append("AGENT_MESSAGE", message.as_payload(), correlation_id)
        return message

    def messages_for(self, agent: str, *, limit: int = 100) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for event in self.journal.read_all():
            if event.get("event_type") != "AGENT_MESSAGE":
                continue
            payload = event.get("payload", {})
            recipients = payload.get("recipients", ())
            if agent not in recipients and "*" not in recipients:
                continue
            rows.append(payload)
        rows.sort(key=lambda item: (-int(item.get("priority", 50)), item.get("created_at", "")))
        return rows[: max(1, int(limit))]

    async def broadcast_roundtable(self, *, chair: str = "GrokBot") -> AgentMessage:
        agents = self.active_agents()
        prompt = {
            "question": "What is the highest-value unresolved observation, evidence gap, test, or blocker in AURELIA right now?",
            "rules": [
                "state evidence, not assumptions",
                "challenge conflicting claims",
                "do not grant capital authority",
                "request missing evidence explicitly",
                "hand off actionable work to the best-suited agent",
            ],
        }
        return await self.publish(
            sender=chair,
            recipients=agents or ("ClaudeCode", "KimiK3", "GrokBot", "GoogleAgentSkills", "GLM", "PlaywrightCLI"),
            message_type="ROUND_TABLE",
            payload=prompt,
            correlation_id=f"roundtable:{int(datetime.now(timezone.utc).timestamp())}",
            priority=80,
            requires_response=True,
        )


class AgentFederationSupervisor:
    def __init__(
        self,
        federation: PersistentAgentFederation,
        *,
        agents: Iterable[str],
        interval_seconds: float = 15.0,
        roundtable_seconds: float = 60.0,
    ) -> None:
        self.federation = federation
        self.agents = tuple(sorted(set(agents)))
        self.interval_seconds = max(2.0, interval_seconds)
        self.roundtable_seconds = max(self.interval_seconds, roundtable_seconds)
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def _cycle(self) -> None:
        last_roundtable = datetime.min.replace(tzinfo=timezone.utc)
        while not self._stop.is_set():
            await self.federation.recover_stale_tasks()
            stale = self.federation.stale_agents()
            for agent in stale:
                if agent not in self.federation._stale_notified:
                    self.federation._append(
                        "AGENT_STALE",
                        {"agent": agent, "action": "RECOVER_ON_NEXT_HEARTBEAT"},
                        correlation_id=f"agent:{agent}",
                    )
                    self.federation._stale_notified.add(agent)
            self.federation._stale_notified.intersection_update(stale)
            active = self.federation.active_agents()
            if datetime.now(timezone.utc) - last_roundtable >= timedelta(seconds=self.roundtable_seconds):
                await self.federation.broadcast_roundtable()
                last_roundtable = datetime.now(timezone.utc)
            await self.federation.publish(
                sender="AURELIA",
                recipients=active or self.agents,
                message_type="CONTINUOUS_WORK_CYCLE",
                payload={
                    "domains": [
                        "market_intelligence",
                        "strategy_review",
                        "validation",
                        "risk_and_execution_review",
                        "security",
                        "deployment",
                        "evidence_reconciliation",
                    ],
                    "capital_authority": False,
                    "status": "SUPERVISED_CONTINUOUS",
                },
                correlation_id=f"cycle:{int(datetime.now(timezone.utc).timestamp())}",
                priority=60,
                requires_response=True,
            )
            for domain, agent in (
                ("research", "KimiK3"),
                ("engineering", "ClaudeCode"),
                ("orchestration", "GrokBot"),
                ("security", "GoogleAgentSkills"),
                ("evidence", "GLM"),
            ):
                # Standing work must be idempotent; do not create a new task
                # every supervisor cycle while a lane is unavailable or busy.
                pending = self.federation.pending_tasks(agent)
                if any(
                    row.get("task_type") == f"CONTINUOUS_{domain.upper()}"
                    for row in pending
                ):
                    continue
                await self.federation.enqueue_task(
                    task_type=f"CONTINUOUS_{domain.upper()}",
                    payload={"domain": domain, "status": "READY", "capital_authority": False},
                    correlation_id=f"standing:{domain}:{agent}",
                    priority=55,
                    assigned_agent=agent,
                )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._cycle(), name="aurelia-agent-federation")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
