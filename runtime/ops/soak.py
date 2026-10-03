from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SoakResult:
    logical_duration_seconds: int
    invariant_violations: int
    silent_degradations: int
    capital_authority_escapes: int
    unresolved_unknown_states: int
    is_production_evidence: bool = False

    @property
    def acceptance_ready(self) -> bool:
        return (
            self.logical_duration_seconds >= 3600
            and self.invariant_violations == 0
            and self.silent_degradations == 0
            and self.capital_authority_escapes == 0
            and self.unresolved_unknown_states == 0
            and self.is_production_evidence
        )


def run_logical_soak(seconds: int, scenario_factory) -> SoakResult:
    '''Run deterministic fault scenarios over logical time.

    This is a test harness, not production soak evidence. Evidence requires
    real elapsed runtime in the target deployment and must set
    is_production_evidence=True only from the approved recorder.
    '''
    violations = silent = escapes = unknowns = 0
    for second in range(seconds):
        state = scenario_factory(second)
        violations += int(state.get("invariant_violation", False))
        silent += int(state.get("silent_degradation", False))
        escapes += int(state.get("capital_authority_escape", False))
        unknowns += int(state.get("unresolved_unknown", False))
    return SoakResult(seconds, violations, silent, escapes, unknowns, False)
