from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecoveryDecision(str, Enum):
    RESUME = "RESUME"
    CAPITAL_PROTECTED = "CAPITAL_PROTECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass(frozen=True)
class RecoveryAssessment:
    broker_outcome_known: bool
    account_verified: bool
    capital_reconciled: bool
    journal_replayed: bool
    authorization_fresh: bool

    def decide(self) -> RecoveryDecision:
        if not self.broker_outcome_known or not self.account_verified or not self.capital_reconciled:
            return RecoveryDecision.CAPITAL_PROTECTED
        if not self.journal_replayed or not self.authorization_fresh:
            return RecoveryDecision.MANUAL_REVIEW
        return RecoveryDecision.RESUME
