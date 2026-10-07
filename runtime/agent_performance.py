from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentEvaluation:
    evaluation_id: str
    agent: str
    task_id: str
    timestamp: float
    category_scores: dict[str, float]
    penalty: float
    evidence_ref: str
    evaluator: str = "AURELIA_DETERMINISTIC_EVALUATOR"

    @property
    def total_points(self) -> float:
        return round(sum(self.category_scores.values()) + self.penalty, 4)


class AgentPerformanceLedger:
    """Evidence-backed reputation ledger; never grants capital authority."""

    LIMITS = {
        "correctness": 25.0,
        "evidence_quality": 20.0,
        "task_outcome": 20.0,
        "robustness": 15.0,
        "reproducibility": 10.0,
        "efficiency": 5.0,
        "collaboration": 5.0,
    }

    def __init__(self, path: str | Path, *, decay_days: float = 90.0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.decay_days = max(1.0, float(decay_days))

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "evaluations": []}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("evaluations"), list):
                return value
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return {"version": 1, "evaluations": []}

    def _save(self, value: dict[str, Any]) -> None:
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(value, sort_keys=True, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def award(self, *, agent: str, task_id: str, category_scores: dict[str, float], evidence_ref: str,
              evaluation_id: str, penalty: float = 0.0,
              evaluator: str = "AURELIA_DETERMINISTIC_EVALUATOR",
              timestamp: float | None = None) -> AgentEvaluation:
        if evaluator != "AURELIA_DETERMINISTIC_EVALUATOR":
            raise PermissionError("ONLY_DETERMINISTIC_EVALUATOR_MAY_AWARD")
        if not agent.strip() or not task_id.strip() or not evidence_ref.strip():
            raise ValueError("AGENT_TASK_AND_EVIDENCE_REQUIRED")
        unknown = set(category_scores) - set(self.LIMITS)
        if unknown:
            raise ValueError(f"UNKNOWN_SCORE_CATEGORY:{sorted(unknown)}")
        bounded = {}
        for key, limit in self.LIMITS.items():
            value = float(category_scores.get(key, 0.0))
            if not math.isfinite(value) or value < 0 or value > limit:
                raise ValueError(f"INVALID_SCORE:{key}")
            bounded[key] = value
        penalty = float(penalty)
        if not math.isfinite(penalty) or penalty > 0 or penalty < -100:
            raise ValueError("INVALID_PENALTY")
        evaluation = AgentEvaluation(evaluation_id, agent, task_id,
                                     float(time.time() if timestamp is None else timestamp),
                                     bounded, penalty, evidence_ref, evaluator)
        data = self._load()
        if any(x.get("evaluation_id") == evaluation_id for x in data["evaluations"]):
            raise ValueError("DUPLICATE_EVALUATION_ID")
        data["evaluations"].append(asdict(evaluation) | {"total_points": evaluation.total_points})
        self._save(data)
        return evaluation

    def leaderboard(self, *, now: float | None = None) -> list[dict[str, Any]]:
        now = float(time.time() if now is None else now)
        half_life = self.decay_days * 86400.0
        agents: dict[str, dict[str, Any]] = {}
        for row in self._load()["evaluations"]:
            weight = math.pow(0.5, max(0.0, now - float(row["timestamp"])) / half_life)
            agent = str(row["agent"])
            bucket = agents.setdefault(agent, {"agent": agent, "decayed_net_points": 0.0,
                "gross_points": 0.0, "evaluations": 0, "positive_evaluations": 0,
                "evidence_quality_rate": 0.0, "successful_task_rate": 0.0})
            total = float(row.get("total_points", sum(row.get("category_scores", {}).values()) + row.get("penalty", 0)))
            bucket["decayed_net_points"] += total * weight
            bucket["gross_points"] += total
            bucket["evaluations"] += 1
            bucket["positive_evaluations"] += int(total > 0)
            bucket["evidence_quality_rate"] += float(row.get("category_scores", {}).get("evidence_quality", 0.0)) / 20.0
            bucket["successful_task_rate"] += float(total > 0)
        for bucket in agents.values():
            n = bucket["evaluations"]
            bucket["decayed_net_points"] = round(bucket["decayed_net_points"], 4)
            bucket["gross_points"] = round(bucket["gross_points"], 4)
            bucket["evidence_quality_rate"] = round(bucket["evidence_quality_rate"] / n, 4)
            bucket["successful_task_rate"] = round(bucket["successful_task_rate"] / n, 4)
        return sorted(agents.values(), key=lambda x: (-x["decayed_net_points"], -x["evidence_quality_rate"], -x["successful_task_rate"], x["agent"]))
\n\nfrom __future__ import annotations

import asyncio
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from runtime.agent_performance import AgentPerformanceLedger


class AgentPerformanceEvaluator:
    """Deterministic bridge from completed federation tasks to reputation."""

    def __init__(self, ledger: AgentPerformanceLedger, *, evidence_root: str | Path | None = None) -> None:
        self.ledger = ledger
        self.evidence_root = Path(evidence_root) if evidence_root else None

    def _evidence_exists(self, ref: str) -> bool:
        if not ref or self.evidence_root is None:
            return bool(ref)
        path = Path(ref)
        if not path.is_absolute():
            path = self.evidence_root / path
        return path.exists() and path.is_file()

    def evaluate(self, *, task_id: str, agent: str, status: str,
                 evidence_ref: str = "", result: dict[str, Any] | None = None,
                 evaluation_id: str | None = None) -> dict[str, Any]:
        result = dict(result or {})
        evidence_ok = self._evidence_exists(evidence_ref)
        completed = status == "COMPLETED"
        failed = status == "FAILED"
        blocked = status == "BLOCKED"
        scores = {
            "correctness": 25.0 if completed and bool(result.get("verified", False)) else 0.0,
            "evidence_quality": 20.0 if evidence_ok else 0.0,
            "task_outcome": 20.0 if completed else 0.0,
            "robustness": 15.0 if completed and bool(result.get("regression_free", False)) else 0.0,
            "reproducibility": 10.0 if completed and bool(result.get("reproducible", False)) else 0.0,
            "efficiency": 5.0 if completed and bool(result.get("efficient", False)) else 0.0,
            "collaboration": 5.0 if completed and bool(result.get("handoff_clean", False)) else 0.0,
        }
        penalty = -20.0 if failed else (-5.0 if blocked else 0.0)
        if completed and not evidence_ok:
            penalty = min(penalty, -25.0)
        evaluation_id = evaluation_id or f"eval:{task_id}:{agent}:{int(time.time() * 1000)}"
        evaluation = self.ledger.award(
            agent=agent,
            task_id=task_id,
            category_scores=scores,
            penalty=penalty,
            evidence_ref=evidence_ref or "MISSING",
            evaluation_id=evaluation_id,
        )
        return asdict(evaluation) | {"total_points": evaluation.total_points}


class PersistentAgentPerformance:
    """Persistent leaderboard facade used by runtime/reporting code."""

    def __init__(self, path: str | Path, *, decay_days: float = 90.0) -> None:
        self.ledger = AgentPerformanceLedger(path, decay_days=decay_days)

    def leaderboard(self) -> list[dict[str, Any]]:
        return self.ledger.leaderboard()
