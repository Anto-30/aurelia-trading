# Stake Policy Provenance Reconciliation

## Authority boundary

This inventory is assurance metadata only. It does not modify
`runtime/core/stake_sizing.py`, set a live stake, create a second daily-loss
guard, or grant capital authority. The canonical `CapitalPlaneExecutor`,
`PersistentDailyRiskGuard`, `LIVE_LOCK`, kill switch and reconciliation
remain sovereign.

A policy can be recorded while incomplete, but it cannot be marked
`VALIDATED` unless its originating source commit, observed commit, approval
authority/date, effective date, source timestamp, intended capital plane and
rationale are all present. A validated policy conflict on one capital plane
blocks resolution.

## Evidence reconciliation as of 2026-11-03

| Amount | Evidence-backed role | Intended plane | Status |
|---:|---|---|---|
| $0.35 | v2.08 research unit; explicitly frozen | RESEARCH | PENDING |
| $1.00 | v2.09 execution minimum / starting stake; owner-authorized v2.08 audit | LIVE | PENDING |
| $1.50 | Previous `v2.08-stake-150` era; not current default | HISTORICAL | PENDING |

The distinction is material: $0.35 is not simply a smaller live minimum. The
Drive `canonical_stake_policy.py` explicitly separates research unit sizes
from execution sizing and states that research units do not authorize
execution. It records `EXECUTION_MINIMUM_STAKE=1.00` and
`DEFAULT_LIVE_STAKE=1.00`, while the main runtime's
`DEFAULT_MINIMUM_STAKE` is also $1.00.

The $1.50 item is referenced as a historical policy era; it is not an
authoritative current policy. The source evidence describes a $1.50 historical
loss. No $5/$10/$15 daily-loss limits are supported by the inspected policy
artifacts, so those values are not registered.

## Provenance gaps

The source file timestamps and the current main baseline commit are preserved
in `config/stake_policy_provenance.json`. The baseline commit is an observed
repository state, not a claim that it introduced the policy value. The
originating commit for all three items remains unknown. The $1.00 audit names
owner authorization and is dated 2026-09-26, but an effective date is not
recorded. The $0.35 and $1.50 items lack a complete approval/effective-date
chain.

Consequently, all three records remain `PENDING`. The registry returns no
authoritative selection for the LIVE plane. Do not promote a candidate merely
because it is the newest or smallest.

## Acceptance conditions

1. Recover the origin commit or signed release record for each policy.
2. Attach approval evidence and effective date, with an identified approver.
3. Confirm the intended capital plane and the code path consuming the value.
4. Independently review the completed provenance chain.
5. Only then mark exactly one policy for that capital plane as validated.

Even a validated stake-policy record does not grant trading authority. All
canonical release, risk, kill-switch, reconciliation and operator
authorization gates still apply.
