# AURELIA Final Operational State — 2026-10-04

## Canonical source

- Repository: `Anto-30/aurelia-trading`
- Branch: `main`
- Current main tip: `7c62c8c7810c5d7d8f2b5f413bcae8a2cce9afae`
- Assurance-validated code baseline: `fce6effab5c3e8ea793856a598c3d89433b3a917`

The current main tip contains evidence-state metadata refreshes after the assurance run. The assurance run itself validated the preceding hardened code baseline `fce6eff…`.

## Engineering verification

The Assurance run `37158183664` / job `111305879006` completed successfully on commit `fce6eff…`.

Verified by the run:

- research, assurance, runtime, and hardening test suites completed successfully
- clean runtime container build completed successfully
- public Deriv market-data WebSocket verification completed successfully
- local worker /health smoke test completed successfully
- certification gate executed and correctly reported production evidence as BLOCKED because required evidence artifacts were absent
- live-release gate executed and correctly remained BLOCKED
- authenticated Deriv real-account verification step was explicitly SKIPPED because CI authentication was not configured

This establishes engineering/CI evidence. It does not establish production deployment, authenticated broker evidence, or live authorization.

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

Current Railway inventory observed through the connected Railway control plane: **0 services**.

The Railway deployment workflow is present and fails closed when `RAILWAY_TOKEN` is unavailable. A previous deployment attempt for this exact project target was rejected because the Railway trial had expired and a plan was required.

No Railway plan was purchased or activated by this work. No Railway token was invented or substituted.

## Deriv state

The repository implementation for the modern Deriv Options API path is verified by code inspection.

Current production authentication status:

`NOT_INDEPENDENTLY_VERIFIED_THIS_CYCLE`

The Assurance run recorded:

`DERIV_AUTH_SESSION=NOT_CONFIGURED`

No private Deriv credential was exposed, committed, or fabricated.

Historical/operator-reported balance information is not treated as current production proof.

## Remaining genuine evidence

The following remain unproven and must come from real operations:

1. Authenticated real-account Deriv session and fresh balance.
2. Real broker proposal/order acknowledgement and broker transaction identifier.
3. Confirmed broker state and authoritative balance movement.
4. Ledger posting and independent reconciliation.
5. Unknown/timeout recovery and restart/reconnect recovery against the real broker.
6. Genuine continuous 3,600-second production-worker soak.
7. Prospective sealed OOS evidence with required Strategy × Symbol × Regime sample sizes.
8. Calibration and drift evidence.
9. Measured net execution economics.
10. Independent security/bypass audit.
11. Build-to-running deployment attestation.
12. Controlled canary evidence.

## Current release verdict

| Gate | Result | Evidence class |
|---|---|---|
| ENGINEERING_READY | PASS | VERIFIED by Assurance CI |
| DEPLOYMENT_READY | PASS | VERIFIED configuration |
| DEPLOYMENT_EXECUTED | FAIL/BLOCKED | NOT EXECUTED |
| AUTHENTICATION_READY — CI | FAIL/BLOCKED | DERIV auth not configured |
| AUTHENTICATION_READY — production worker | BLOCKED | No worker deployment |
| BROKER_EVIDENCE_READY | FAIL/BLOCKED | No real lifecycle executed this cycle |
| PRODUCTION_SOAK_READY | PASS for harness | TESTED, non-production |
| PRODUCTION_SOAK_COMPLETED | FAIL/BLOCKED | NOT EXECUTED |
| STRATEGY_LIVE_ELIGIBLE | FAIL/BLOCKED | Qualification evidence incomplete |
| LIVE_AUTHORIZED | FAIL by design | VERIFIED fail-closed |

## External activation sequence

1. Activate the Railway plan externally.
2. Enable the existing project to create exactly one `aurelia-production-worker` service in `production`.
3. Configure `RAILWAY_TOKEN` as a protected secret; never place its value in source or chat.
4. Configure Deriv production credentials through the secure secret mechanism expected by the runtime.
5. Run authenticated Deriv verification.
6. Deploy the existing worker while `LIVE_EXECUTION=BLOCKED`.
7. Verify deployment lineage, runtime health, and protected state.
8. Execute the genuine broker/recovery/evidence cycle.
9. Run and observe the complete 3,600-second production-worker soak.
10. Review the sealed evidence bundle and perform a separate capital authorization review.

## Non-negotiable controls

Unknown broker outcomes never become safe-to-retry by assumption.

Verified balance controls affordability; it does not grant authority.

Model or agent output never becomes execution authorization.

Deployment never becomes live authorization.

A passing test proves only the scenario it exercised.

The system remains fail-closed until genuine external evidence satisfies the applicable gates.
