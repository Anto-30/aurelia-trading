"""Dual-primary intelligence council for AURELIA.

ChatGPT and Claude Code are peers at the intelligence layer. The council never
authorizes capital, mutates LIVE_LOCK, or bypasses deterministic controls.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class BrainStatus:
    brain: str
    available: bool
    reason: str

@dataclass(frozen=True)
class BrainDecision:
    status: str
    primary: str | None
    challenger: str | None
    require_both: bool
    reason: str

PRIMARY_BRAINS = ("ChatGPT", "ClaudeCode")

class BrainCouncil:
    def __init__(self, statuses: Iterable[BrainStatus]) -> None:
        self.statuses = {s.brain: s for s in statuses}

    def decide(self, *, capital_relevant: bool = False, high_consequence: bool = False) -> BrainDecision:
        available = [
            name for name in PRIMARY_BRAINS
            if self.statuses.get(name, BrainStatus(name, False, "UNVERIFIED")).available
        ]
        if not available:
            return BrainDecision("ABSTAIN", None, None, True, "NO_VERIFIED_PRIMARY_BRAIN")
        if capital_relevant or high_consequence:
            if len(available) < 2:
                return BrainDecision("ABSTAIN", None, None, True, "DUAL_PRIMARY_BRAIN_REQUIRED")
            return BrainDecision("DUAL_ROUTE", available[0], available[1], True, "INDEPENDENT_PRIMARY_BRAIN_REVIEW")
        if len(available) == 2:
            return BrainDecision("ROUTE", "ChatGPT", "ClaudeCode", False, "DUAL_PRIMARY_AVAILABLE")
        return BrainDecision("ROUTE", available[0], None, False, "SINGLE_PRIMARY_AVAILABLE")
