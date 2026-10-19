"""Research-only BRAIN/REFLEX boundary for Deriv paper evaluation.

This package has no broker client and no capital or order-submission authority.
"""
from .agent import PaperAgent, PaperEvaluation
from .decision import JevDecision, DecisionSchemaError
from .ledger import PaperEventLedger
from .risk import PaperReflexGate, PortfolioRiskSnapshot, GateResult

RESEARCH_ONLY = True
CAPITAL_AUTHORITY = False
ORDER_SUBMISSION_PERMITTED = False

__all__ = [
    "PaperAgent", "PaperEvaluation", "JevDecision", "DecisionSchemaError",
    "PaperEventLedger", "PaperReflexGate", "PortfolioRiskSnapshot", "GateResult",
    "RESEARCH_ONLY", "CAPITAL_AUTHORITY", "ORDER_SUBMISSION_PERMITTED",
]
