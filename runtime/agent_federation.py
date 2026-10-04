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
    heartbeat_at: datetime
    expires_at: datetime

    @property
    def active(self) -> bool:
        return datetime.now(timezone.utc) < self.expires_at


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
    ) -> None:
        self.journal = AppendOnlyJournal(journal_path)
        self.lease_path = Path(lease_path)
        self.lease_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_hash = config_hash
        self.source_hash = source_hash
        self.lease_seconds = max(5.0, lease_seconds)
        self._lock = asyncio.Lock()

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

    def _save_leases(self, leases: dict[str, dict[str, str]]) -> None:
        temp = self.lease_path.with_suffix(self.lease_path.suffix + ".tmp")
        temp.write_text(json.dumps({"version": 1, "leases": leases}, sort_keys=True), encoding="utf-8")
        temp.replace(self.lease_path)

    async def heartbeat(self, agent: str) -> AgentLease:
        now = datetime.now(timezone.utc)
        lease = AgentLease(
            agent=agent,
            lease_id=f"lease:{agent}:{int(now.timestamp() * 1000)}",
            heartbeat_at=now,
            expires_at=now + timedelta(seconds=self.lease_seconds),
        )
        async with self._lock:
            leases = self._load_leases()
            leases[agent] = {
                "lease_id": lease.lease_id,
                "heartbeat_at": lease.heartbeat_at.isoformat(),
                "expires_at": lease.expires_at.isoformat(),
            }
            self._save_leases(leases)
        self._append(
            "AGENT_HEARTBEAT",
            {"agent": agent, "lease_id": lease.lease_id, "expires_at": lease.expires_at.isoformat()},
            correlation_id=f"agent:{agent}",
        )
        return lease

    async def register_agents(self, agents: Iterable[str]) -> None:
        for agent in agents:
            await self.heartbeat(agent)

    def active_agents(self) -> tuple[str, ...]:
        leases = self._load_leases()
        now = datetime.now(timezone.utc)
        return tuple(
            sorted(
                agent
                for agent, value in leases.items()
                if datetime.fromisoformat(value["expires_at"]) > now
            )
        )

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
        message = AgentMessage(
            message_id=f"msg:{sha256({'sender': sender, 'recipients': recipients_tuple, 'message_type': message_type, 'payload': payload, 'created_at': now.isoformat()})}",
            sender=sender,
            recipients=recipients_tuple,
            message_type=message_type,
            payload=payload,
            created_at=now,
            correlation_id=correlation_id,
            priority=max(0, min(100, int(priority))),
            requires_response=requires_response,
        )
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
            await self.federation.register_agents(self.agents)
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
                    "status": "ACTIVE",
                },
                correlation_id=f"cycle:{int(datetime.now(timezone.utc).timestamp())}",
                priority=60,
                requires_response=True,
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
