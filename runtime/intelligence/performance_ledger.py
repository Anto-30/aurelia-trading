"""Append-only model/agent performance ledger primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvaluationRecord:
    task_id: str
    agent_id: str
    model_id: str
    model_version: str
    task_type: str
    correctness: float | None
    calibration: float | None
    robustness: float | None
    evidence_quality: float | None
    latency_ms: float | None
    cost: float | None
    failure_type: str | None
    review_result: str
    created_at_utc: str

    @classmethod
    def create(cls, **kwargs: Any) -> "EvaluationRecord":
        kwargs.setdefault("created_at_utc", datetime.now(timezone.utc).isoformat())
        return cls(**kwargs)


class PerformanceLedger:
    """Append-only JSONL store. Existing records are never rewritten."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: EvaluationRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(json.loads(line))
        return records
