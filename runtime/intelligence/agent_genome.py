"""Versioned agent capability passport / genome."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass
class AgentGenome:
    agent_id: str
    role: str
    model_id: str
    model_version: str
    capabilities: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    failure_patterns: list[str] = field(default_factory=list)
    collaborators: list[str] = field(default_factory=list)
    validated_knowledge_ids: list[str] = field(default_factory=list)
    experimental_knowledge_ids: list[str] = field(default_factory=list)
    prohibited_actions: list[str] = field(default_factory=list)
    version: int = 1

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)


def save_genome(path: str | Path, genome: AgentGenome) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(genome.snapshot(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
