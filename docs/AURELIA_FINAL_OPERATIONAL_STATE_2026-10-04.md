# AURELIA Final Operational State — 2026-10-04

## Canonical source

- Repository: `Anto-30/aurelia-trading`
- Branch: `main`
- Verified head commit: `e9d1f7a9a96cf9cdfbaec3aecb099c8a60112978`

## Completed engineering work

The current branch contains the hardened capital boundary, strict evidence provenance, deterministic evidence hashing, broker unknown-outcome recovery, serialized execution, kill-switch freshness requirements, readiness evidence validation, and a fail-closed live-release gate.

The Assurance workflow on the verified head commit completed successfully with:

- 14 research tests
- 32 assurance tests
- 88 runtime tests
- 12 hardening tests
- clean runtime container build
- public Deriv market-data WebSocket verification
- worker health smoke test
- certification-gate execution
- standalone live-release fail-closed verification

Total: 146 automated tests.

## Current capital state

`config/LIVE_LOCK.yaml` remains:

- `live_trading_enabled: false`
- `FINAL_EXECUTION_AUTHORIZATION: false`
- `LIVE_EXECUTION: BLOCKED`
- `capital_plane_mode: VERIFY_ONLY`

No live order has been submitted by this work.

## Railway state

Project: `AURELIA-Production-Worker`

Environment: `production`

Required service: `aurelia-production-worker`

Current Railway inventory: no services.

The GitHub deployment workflow correctly fails closed when `RAILWAY_TOKEN` is unavailable. The latest deployment workflow therefore proves the external blocker was detected and capital protection remained intact; it does not represent a successful Railway deployment.

Direct Railway mutation was also attempted for the exact repository/project/service target and was rejected by Railway because the account trial has expired and a plan must be selected.

## Remaining genuine evidence

The following must come from real operations and must not be fabricated:

1. Authenticated real-account Deriv session and fresh balance.
2. Broker proposal/order acknowledgement and broker transaction identifier.
3. Confirmed broker state and authoritative balance movement.
4. Ledger posting and independent reconciliation.
5. Unknown/timeout recovery and restart/reconnect recovery against the real broker.
6. Genuine continuous 3,600-second non-live production-deployment soak.
7. Prospective sealed OOS evidence with required Strategy x Symbol x Regime sample sizes.
8. Calibration/drift evidence.
9. Measured net execution economics.
10. Independent security/bypass audit.
11. Build-to-running deployment attestation.
12. Controlled canary evidence.

## Exact external activation sequence

1. Activate a Railway plan so the existing project can create/deploy services.
2. Provide Railway with permission to use the connected GitHub repository and create the exact service `aurelia-production-worker` in `production`.
3. Configure `RAILWAY_TOKEN` as a protected GitHub Actions secret.
4. Configure Deriv production credentials as protected Railway/GitHub secrets; never commit or paste them into source.
5. Run the authenticated Deriv verification workflow.
6. Deploy the worker while `LIVE_EXECUTION=BLOCKED`.
7. Run the real deployment soak/recovery/evidence workflows.
8. Review the sealed evidence bundle.
9. Perform a separate capital authorization review.
10. Do not enable live capital merely because CI, deployment, or a single successful trade passes.

## Non-negotiable controls

Unknown broker outcome never becomes safe-to-retry by assumption.

Verified balance controls affordability; it does not grant authority.

Model or agent output never becomes execution authorization.

Deployment never becomes live authorization.

A passing test proves only the scenario it exercised.

The system remains fail-closed until genuine external evidence satisfies the applicable gates.
