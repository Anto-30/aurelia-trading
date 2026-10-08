from __future__ import annotations

import hashlib
import json
import math
import os
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
    evidence_sha256: str | None = None
    evidence_size_bytes: int | None = None
    status: str = "COMPLETED"
    evaluator: str = "AURELIA_DETERMINISTIC_EVALUATOR"

    @property
    def total_points(self) -> float:
        return round(sum(self.category_scores.values()) + self.penalty, 4)


class AgentPerformanceLedger:
    """Evidence-backed reputation ledger; never grants capital authority."""

    LIMITS = {"correctness": 25.0, "evidence_quality": 20.0, "task_outcome": 20.0,
              "robustness": 15.0, "reproducibility": 10.0, "efficiency": 5.0, "collaboration": 5.0}

    def __init__(self, path: str | Path, *, decay_days: float = 90.0) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.decay_days = max(1.0, float(decay_days))

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 2, "evaluations": []}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and isinstance(value.get("evaluations"), list):
                return value
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return {"version": 2, "evaluations": []}

    def _save(self, value: dict[str, Any]) -> None:
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(value, sort_keys=True, indent=2), encoding="utf-8")
        temp.replace(self.path)

    @staticmethod
    def evidence_metadata(ref: str) -> tuple[str | None, int | None]:
        path = Path(ref) if ref and ref != "MISSING" else None
        if path is None or not path.is_file():
            return None, None
        digest, size = hashlib.sha256(), 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    def award(self, *, agent: str, task_id: str, category_scores: dict[str, float],
              evidence_ref: str, evaluation_id: str, penalty: float = 0.0,
              status: str = "COMPLETED", evidence_sha256: str | None = None,
              evidence_size_bytes: int | None = None,
              evaluator: str = "AURELIA_DETERMINISTIC_EVALUATOR",
              timestamp: float | None = None) -> AgentEvaluation:
        if evaluator != "AURELIA_DETERMINISTIC_EVALUATOR":
            raise PermissionError("ONLY_DETERMINISTIC_EVALUATOR_MAY_AWARD")
        if not agent.strip() or not task_id.strip() or not evidence_ref.strip():
            raise ValueError("AGENT_TASK_AND_EVIDENCE_REQUIRED")
        if status not in {"COMPLETED", "FAILED", "BLOCKED"}:
            raise ValueError("INVALID_EVALUATION_STATUS")
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
        if evidence_sha256 is None:
            evidence_sha256, evidence_size_bytes = self.evidence_metadata(evidence_ref)
        evaluation = AgentEvaluation(evaluation_id, agent, task_id,
                                     float(time.time() if timestamp is None else timestamp),
                                     bounded, penalty, evidence_ref, evidence_sha256,
                                     evidence_size_bytes, status, evaluator)
        data = self._load()
        if any(x.get("evaluation_id") == evaluation_id for x in data["evaluations"]):
            raise ValueError("DUPLICATE_EVALUATION_ID")
        data["version"] = max(2, int(data.get("version", 1)))
        data["evaluations"].append(asdict(evaluation) | {"total_points": evaluation.total_points})
        self._save(data)
        return evaluation

    def evaluations_for(self, agent: str | None = None) -> list[dict[str, Any]]:
        rows = [dict(x) for x in self._load()["evaluations"]
                if agent is None or str(x.get("agent")) == agent]
        return sorted(rows, key=lambda x: (-float(x.get("timestamp", 0)), str(x.get("evaluation_id", ""))))

    def leaderboard(self, *, now: float | None = None) -> list[dict[str, Any]]:
        now = float(time.time() if now is None else now)
        half_life = self.decay_days * 86400.0
        agents: dict[str, dict[str, Any]] = {}
        for row in self._load()["evaluations"]:
            weight = math.pow(0.5, max(0.0, now - float(row["timestamp"])) / half_life)
            agent = str(row["agent"])
            b = agents.setdefault(agent, {"agent": agent, "decayed_net_points": 0.0,
                "gross_points": 0.0, "positive_evaluations": 0, "evaluations": 0,
                "successful_tasks": 0, "completed_tasks": 0, "failed_tasks": 0,
                "blocked_tasks": 0, "penalty_points": 0.0, "evidence_quality_rate": 0.0,
                "successful_task_rate": 0.0, "_last_timestamp": None})
            total = float(row.get("total_points", sum(row.get("category_scores", {}).values()) + row.get("penalty", 0)))
            status = str(row.get("status", "COMPLETED"))
            b["decayed_net_points"] += total * weight
            b["gross_points"] += total
            b["evaluations"] += 1
            b["positive_evaluations"] += int(total > 0)
            b["penalty_points"] += float(row.get("penalty", 0))
            b["evidence_quality_rate"] += float(row.get("category_scores", {}).get("evidence_quality", 0)) / 20.0
            b["completed_tasks"] += int(status == "COMPLETED")
            b["failed_tasks"] += int(status == "FAILED")
            b["blocked_tasks"] += int(status == "BLOCKED")
            b["successful_tasks"] += int(status == "COMPLETED" and total > 0)
            ts = float(row.get("timestamp", 0))
            if b["_last_timestamp"] is None or ts > b["_last_timestamp"]:
                b["_last_timestamp"] = ts
        for b in agents.values():
            n, completed = b["evaluations"], b["completed_tasks"]
            b["decayed_net_points"] = round(b["decayed_net_points"], 4)
            b["gross_points"] = round(b["gross_points"], 4)
            b["penalty_points"] = round(b["penalty_points"], 4)
            b["evidence_quality_rate"] = round(b["evidence_quality_rate"] / n, 4) if n else 0.0
            b["successful_task_rate"] = round(b["successful_tasks"] / completed, 4) if completed else 0.0
            b["last_evaluation_at"] = b.pop("_last_timestamp")
            b["leadership_eligible"] = n >= 10
        rows = sorted(agents.values(), key=lambda x: (-x["decayed_net_points"],
            -x["evidence_quality_rate"], -x["successful_task_rate"], x["agent"]))
        for rank, row in enumerate(rows, 1):
            row["rank"] = rank
        return rows

    def snapshot(self, *, now: float | None = None, agent: str | None = None) -> dict[str, Any]:
        rows = self.leaderboard(now=now)
        if agent:
            rows = [x for x in rows if x["agent"] == agent]
        return {"version": 1, "generated_at": float(time.time() if now is None else now),
                "decay_half_life_days": self.decay_days,
                "ranking": ["decayed_net_points", "evidence_quality_rate", "successful_task_rate"],
                "agents": rows, "evidence": self.evaluations_for(agent),
                "capital_authority": False, "live_execution_authority": False}


class AgentPerformanceEvaluator:
    """Deterministic bridge from completed federation tasks to reputation."""

    PENALTIES = {"fabricated_evidence": -100.0, "false_completion": -75.0, "regression": -50.0,
                 "invalid_research_claim": -50.0, "control_bypass_attempt": -100.0,
                 "repeated_unresolved_error": -20.0}

    def __init__(self, ledger: AgentPerformanceLedger, *, evidence_root: str | Path | None = None) -> None:
        self.ledger = ledger
        self.evidence_root = Path(evidence_root or os.getenv("AURELIA_EVIDENCE_ROOT", "/var/lib/aurelia/evidence"))

    def _resolve_evidence(self, ref: str) -> Path | None:
        if not ref or ref == "MISSING":
            return None
        path = Path(ref)
        if not path.is_absolute():
            path = self.evidence_root / path
        return path if path.is_file() else None

    def evaluate(self, *, task_id: str, agent: str, status: str, evidence_ref: str = "",
                 result: dict[str, Any] | None = None, evaluation_id: str | None = None) -> dict[str, Any]:
        result = dict(result or {})
        evidence_path = self._resolve_evidence(evidence_ref)
        evidence_ok = evidence_path is not None
        completed, failed, blocked = status == "COMPLETED", status == "FAILED", status == "BLOCKED"
        scores = {"correctness": 25.0 if completed and evidence_ok and result.get("verified") else 0.0,
                  "evidence_quality": 20.0 if evidence_ok else 0.0,
                  "task_outcome": 20.0 if completed and evidence_ok else 0.0,
                  "robustness": 15.0 if completed and evidence_ok and result.get("regression_free") else 0.0,
                  "reproducibility": 10.0 if completed and evidence_ok and result.get("reproducible") else 0.0,
                  "efficiency": 5.0 if completed and evidence_ok and result.get("efficient") else 0.0,
                  "collaboration": 5.0 if completed and evidence_ok and result.get("handoff_clean") else 0.0}
        penalty = -20.0 if failed else (-5.0 if blocked else 0.0)
        penalty_reason = "FAILED_TASK" if failed else ("BLOCKED_TASK" if blocked else "")
        for reason, value in self.PENALTIES.items():
            if result.get(reason):
                penalty, penalty_reason = min(penalty, value), reason
        if completed and not evidence_ok:
            penalty, penalty_reason = -25.0, "COMPLETED_WITHOUT_VERIFIABLE_EVIDENCE"
        evaluation_id = evaluation_id or f"eval:{task_id}:{agent}:{int(time.time() * 1000)}"
        sha256, size = AgentPerformanceLedger.evidence_metadata(str(evidence_path)) if evidence_path else (None, None)
        evaluation = self.ledger.award(agent=agent, task_id=task_id, category_scores=scores,
            penalty=penalty, status=status, evidence_ref=evidence_ref or "MISSING",
            evaluation_id=evaluation_id, evidence_sha256=sha256, evidence_size_bytes=size)
        return asdict(evaluation) | {"total_points": evaluation.total_points, "penalty_reason": penalty_reason}


class PersistentAgentPerformance:
    def __init__(self, path: str | Path, *, decay_days: float = 90.0) -> None:
        self.ledger = AgentPerformanceLedger(path, decay_days=decay_days)

    def leaderboard(self) -> list[dict[str, Any]]:
        return self.ledger.leaderboard()

    def snapshot(self, *, agent: str | None = None) -> dict[str, Any]:
        return self.ledger.snapshot(agent=agent)
