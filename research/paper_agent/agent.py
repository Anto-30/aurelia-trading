"""Non-executing REFLEX adapter: validates proposals and records dispositions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .decision import DecisionSchemaError, JevDecision
from .ledger import PaperEventLedger
from .risk import PaperReflexGate, PortfolioRiskSnapshot, StrategyEvidence


@dataclass(frozen=True)
class PaperEvaluation:
    event_id: str
    status: str
    reasons: tuple[str, ...]
    kill_switch_tripped: bool


class PaperAgent:
    """Validate BRAIN/Jev candidates, apply gates, and log dispositions.

    This deliberately has no Deriv client, order method, fill simulator, or live
    mode. An accepted result means only "would trade if a separately verified
    paper contract simulator and release process were attached."
    """

    research_only = True
    capital_authority = False
    order_submission_permitted = False

    def __init__(self, gate: PaperReflexGate, ledger: PaperEventLedger) -> None:
        self.gate = gate
        self.ledger = ledger

    def on_api_error(self, *, event_id: str) -> PaperEvaluation:
        self.gate.on_api_error()
        row = self.ledger.append(
            event_id=event_id,
            event_type="KILL_SWITCH_TRIPPED",
            payload={
                "reason": "API_ERROR", "capital_authority": False,
                "order_submission_permitted": False,
            },
        )
        return PaperEvaluation(
            event_id=row["event_id"], status="BLOCKED",
            reasons=("API_ERROR", "KILL_SWITCH_LATCHED"), kill_switch_tripped=True,
        )

    def evaluate(
        self, *, event_id: str, candidate: Mapping[str, Any],
        snapshot: PortfolioRiskSnapshot,
        strategy_evidence: StrategyEvidence | None = None,
        strategy_hash: str | None = None,
    ) -> PaperEvaluation:
        try:
            decision = JevDecision.from_mapping(candidate)
        except DecisionSchemaError as exc:
            reason = str(exc)
            row = self.ledger.append(
                event_id=event_id,
                event_type="MISSED_SIGNAL",
                payload={
                    "status": "BLOCKED", "reason": reason,
                    "capital_authority": False, "order_submission_permitted": False,
                },
            )
            return PaperEvaluation(
                row["event_id"], "BLOCKED", (reason,), self.gate.tripped
            )

        result = self.gate.evaluate(
            decision, snapshot, evidence=strategy_evidence,
            expected_strategy_hash=strategy_hash,
        )
        if result.allowed:
            event_type = "PAPER_INTENT"
        elif decision.direction != "neutral":
            event_type = "MISSED_SIGNAL"
        else:
            event_type = "DECISION_EVALUATED"

        row = self.ledger.append(
            event_id=event_id,
            event_type=event_type,
            payload={
                "decision": decision.as_dict(),
                "strategy_hash": strategy_hash,
                "strategy_evidence": strategy_evidence.as_dict() if strategy_evidence is not None else None,
                "status": result.status,
                "allowed_by_risk_gate": result.allowed,
                "reasons": list(result.reasons),
                "kill_switch_tripped": result.kill_switch_tripped,
                "capital_authority": False,
                "order_submission_permitted": False,
                "real_fill": False,
                "simulated_pnl": None,
            },
        )
        return PaperEvaluation(
            event_id=row["event_id"], status=result.status,
            reasons=result.reasons, kill_switch_tripped=result.kill_switch_tripped,
        )

    def reset_after_operator_review(
        self, *, event_id: str, operator_approval_id: str,
        snapshot: PortfolioRiskSnapshot, crisis_cleared: bool,
        confidence_recovered: bool,
    ) -> None:
        self.gate.reset_after_operator_review(
            operator_approval_id=operator_approval_id,
            snapshot=snapshot, crisis_cleared=crisis_cleared,
            confidence_recovered=confidence_recovered,
        )
        self.ledger.append(
            event_id=event_id, event_type="KILL_SWITCH_RESET",
            payload={
                "operator_approval_id": operator_approval_id,
                "reason": "OPERATOR_REVIEWED",
                "capital_authority": False, "order_submission_permitted": False,
            },
        )
