"""Validation of recorded AURELIA adversarial soak evidence.

This module does not sleep for 3,600 seconds and does not simulate a runtime.
It validates evidence from a genuinely executed non-live soak.
"""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class SoakResult:
    duration_seconds: int
    invariant_violations: int
    blind_resubmissions: int
    duplicate_economic_effects: int
    capital_authority_escapes: int
    unexplained_shadow_divergences: int
    silent_degradations: int
    unresolved_unknown_states: int

def validate_full_soak(result: SoakResult) -> bool:
    return (
        result.duration_seconds >= 3600
        and result.invariant_violations == 0
        and result.blind_resubmissions == 0
        and result.duplicate_economic_effects == 0
        and result.capital_authority_escapes == 0
        and result.unexplained_shadow_divergences == 0
        and result.silent_degradations == 0
        and result.unresolved_unknown_states == 0
    )

def smoke_soak_is_not_full_soak(result: SoakResult) -> bool:
    return result.duration_seconds < 3600
