# AURELIA Runtime Control Matrix — 2026-10-03

| Control | Enforcement | Failure |
|---|---|---|
| Account identity | Expected loginid/currency binding | ACCOUNT_IDENTITY_MISMATCH |
| Capital freshness | Bounded freshness and finite numeric checks | CAPITAL_TRUTH_NOT_FRESH |
| Probability | Hard 0.55–0.75; no clipping | PROBABILITY_OUTSIDE_HARD_POLICY |
| Stake floor | $1.50 order-level minimum | STAKE_NOT_AFFORDABLE_OR_BELOW_BROKER_MINIMUM |
| Stake ceiling | Requested stake <= verified available balance | STAKE_NOT_AFFORDABLE_OR_BELOW_BROKER_MINIMUM |
| Risk | Explicit risk approval input | RISK_WARDEN_REJECTED |
| Firewall | Explicit execution approval input | EXECUTION_FIREWALL_REJECTED |
| Kill switch | Checked immediately before broker submission | KILL_SWITCH_ON |
| Authorization lease | Expiring authorization context | STALE_AUTHORIZATION |
| Broker uncertainty | UNKNOWN becomes recovery | BROKER_OUTCOME_UNKNOWN |
| Single writer | Fencing token | STALE_EXECUTOR_FENCE |
| Idempotency | One intent, max one economic effect | DUPLICATE_ECONOMIC_EFFECT |
| Proposal identity | Broker proposal ID is required | PROPOSAL_ID_MISSING |
| Reconciliation | Broker capital compared with expected state | CAPITAL_MISMATCH |
| Research boundary | Research has no capital authority | RESEARCH_CAPITAL_FORBIDDEN |
| Deployment | Source/build/artifact/config lineage | PROVENANCE_GAP |
| Evidence | Missing/expired evidence stays blocked | CERTIFICATION_NOT_READY |