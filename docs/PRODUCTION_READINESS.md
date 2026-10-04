# AURELIA Production Readiness

AURELIA uses evidence-backed release authorization. Credentials, process health,
unit-test success, or dashboard state are not capital authorization.

## Required progression

1. Engineering assurance is green for the exact source commit.
2. A governed persistent deployment is healthy and source-integrity verified.
3. Real Deriv authentication, account identity, currency and fresh balance are verified.
4. The verify-only broker lifecycle proves proposal, authorization, fencing,
   idempotency and reconciliation without capital movement.
5. Prospective OOS, calibration, execution economics, security and 3600-second
   soak evidence are independently generated and validated.
6. Decision-time controls independently verify fresh market data, probability,
   capital, configuration and deployment state.
7. The release gate evaluates the complete evidence bundle.
8. A canary is limited to one broker-permitted minimum-stake transaction and
   must reconcile completely before broader production use.

## Fail-closed rules

Unknown broker outcome, stale evidence, configuration drift, deployment drift,
unexpected balance delta, unresolved reconciliation, stale probability, market
data uncertainty, kill-switch activation, and circuit-breaker trips all mean NO TRADE.

Research agents, external repositories, dashboards and advisory agents cannot
authorize capital.

## Deployment providers

Railway is optional. OCI is an equivalent governed deployment target when its
secrets, source lineage and health checks are independently verified. A
provider-specific outage must not be converted into a capital-control bypass.

## Credential handling

Raw credentials remain in the protected deployment secret boundary. Evidence
contains only derived identity/state and hashes required for provenance; tokens
are never logged, committed, or copied into general-purpose storage.
