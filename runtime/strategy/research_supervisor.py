from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.agent_federation import PersistentAgentFederation
from runtime.strategy.autonomous_signal_engine import AutonomousSignalHunter


@dataclass
class ResearchSignalSupervisor:
    adapter: DerivAdapter
    federation: PersistentAgentFederation
    symbols: tuple[str, ...]
    hunter: AutonomousSignalHunter

    async def run(self) -> None:
        streams = [self.adapter.subscribe_ticks(symbol) for symbol in self.symbols]
        iterators = [stream.__aiter__() for stream in streams]
        recipients = ("ClaudeCode", "KimiK3", "GrokBot", "AURELIA")
        while True:
            tasks = [asyncio.create_task(it.__anext__()) for it in iterators]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                try:
                    tick = task.result()
                except StopAsyncIteration:
                    continue
                candidate = self.hunter.observe(
                    symbol=tick.symbol,
                    quote=tick.quote,
                    received_at=tick.received_at,
                )
                if candidate is None:
                    continue
                payload = self.hunter.as_message_payload(candidate)
                payload["account_loginid"] = "RESEARCH_UNBOUND"
                await self.federation.publish(
                    sender="AURELIA",
                    recipients=recipients,
                    message_type="RESEARCH_SIGNAL_CANDIDATE",
                    payload=payload,
                    correlation_id=f"research-signal:{candidate.symbol}:{int(candidate.created_at.timestamp())}",
                    priority=60,
                    requires_response=False,
                )

    def start_task(self) -> asyncio.Task[None]:
        return asyncio.create_task(self.run(), name="aurelia-research-signal-supervisor")


def build_research_signal_supervisor(
    adapter: DerivAdapter,
    federation: PersistentAgentFederation,
    symbols: tuple[str, ...],
) -> ResearchSignalSupervisor:
    return ResearchSignalSupervisor(
        adapter=adapter,
        federation=federation,
        symbols=symbols,
        hunter=AutonomousSignalHunter(
            window=int(os.getenv("AURELIA_SIGNAL_WINDOW", "64")),
            min_observations=int(os.getenv("AURELIA_SIGNAL_MIN_OBSERVATIONS", "20")),
            threshold=float(os.getenv("AURELIA_SIGNAL_THRESHOLD", "1.5")),
            cooldown_seconds=float(os.getenv("AURELIA_SIGNAL_COOLDOWN_SECONDS", "30")),
        ),
    )
