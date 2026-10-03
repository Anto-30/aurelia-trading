# AURELIA Adversarial Soak Protocol

## Objective

Prove that the non-live execution control path preserves capital-integrity invariants continuously for 3,600 seconds while deliberately encountering uncertainty, concurrency, stale state, restarts and reconciliation failures.

## Required runtime conditions

The authoritative AURELIA runtime must be recovered and executed in a non-live environment using the same deterministic control path intended for production. No broker-capital submission is permitted.

## Injected faults

At minimum inject:
- stale and duplicated market data;
- out-of-order events;
- WebSocket interruption;
- request timeout;
- response loss after a simulated economic effect;
- unknown broker state;
- duplicate intent;
- concurrent intent;
- crash at each material lifecycle transition;
- restart with kill switch on;
- stale authorization;
- configuration mismatch;
- account mismatch;
- insufficient funds;
- ledger/reconciliation mismatch;
- backup/restore;
- credential boundary violation;
- shadow-path divergence.

## Pass criteria

INVARIANT_VIOLATIONS == 0

BLIND_RESUBMISSIONS == 0

DUPLICATE_ECONOMIC_EFFECTS == 0

CAPITAL_AUTHORITY_ESCAPES == 0

UNEXPLAINED_SHADOW_DIVERGENCES == 0

SILENT_DEGRADATIONS == 0

UNRESOLVED_UNKNOWN_STATES == 0 at termination

The run must be genuinely continuous for 3,600 seconds. A unit-test suite or a short smoke run is not equivalent evidence.

## Evidence

Emit a machine-readable evidence envelope containing source, artifact, configuration and data hashes; start/end timestamps; environment; scenario injections; invariant results; correlation IDs; and final record hash.

## Current status

Until the authoritative runtime source is recovered and the full continuous run is actually executed, this requirement is NOT_RUN / UNPROVEN.
