# AURELIA Autonomous Operating Contract — 2026-10-03

Status: design/control contract. This document does not authorize live capital.

## 1. Purpose
Define the conditions under which the existing AURELIA architecture may progress from research/verification into controlled autonomous execution. This supplements the existing assurance plane and does not create a second trading engine.

## 2. Authority model
The capital plane is the only plane permitted to authorize or submit broker orders. Research, counselling, Grok, Dev, external repositories, dashboards, cached state, and historical status files have no capital authority. Final execution is the conjunction of all mandatory controls; no model, agent, UI action, strategy signal, or passing test may override a failed control.

## 3. Authoritative state
Capital truth follows: account identity → fresh broker balance → open exposure → execution intents → broker transaction identifiers → settlement → internal ledger → reconciliation. Cached UI state is informational only. Stale, missing, contradictory, or unverified capital cannot authorize an order.

## 4. Execution evidence
Every live-capable decision must preserve immutable evidence sufficient to reconstruct decision ID/time, strategy/configuration version and hash, symbol and market-data timestamps, probability and validation status, risk/exposure, requested and approved stake, broker request/response and transaction ID, latency, execution economics, settlement, ledger result, and reconciliation status.

## 5. Capital and stake semantics
EXECUTION_MINIMUM_STAKE = 1.50 is an order-level broker minimum, not a global production-readiness gate. STAKE_CEILING = AUTHORITATIVE_VERIFIED_AVAILABLE_BALANCE. Affordability is evaluated at execution time. Risk controls may reduce the stake. Full-balance affordability never authorizes a trade by itself.

## 6. Probability policy
MIN_TRADE_PROBABILITY = 0.55 and MAX_TRADE_PROBABILITY = 0.75 are hard bounds. Values outside the interval are invalid for trading and are not clipped. Uncalibrated, stale, drifted, or otherwise invalid probability evidence results in no-trade.

## 7. Strategy immutability
A strategy, feature definition, data version, configuration, or execution dependency must be content-addressed for validation. Changing a validation-relevant artifact creates a new version and invalidates dependent evidence. Live validation must not silently mutate strategy logic.

## 8. Incident state machine
Operational lifecycle: HEALTHY → DEGRADED → CAPITAL_PROTECTED → RECOVERY → VERIFIED → RESUME. Broker/session loss, stale or contradictory balance, reconciliation mismatch, duplicate/ambiguous transaction, corrupted/missing state, clock failure, market-data failure, watchdog/risk/firewall failure, or expired authorization/evidence must enter a protective state. Restarting alone is not recovery.

## 9. Transaction lifecycle
Every order-capable intent must be idempotent across retries and process restarts. Required lifecycle: intent → authorization → submission → broker acknowledgement → result/settlement → ledger → reconciliation. An ambiguous broker outcome enters recovery. Blind resubmission is prohibited.

## 10. Restart and concurrency
The native runtime must test termination before submission; termination after submission but before acknowledgement; lost broker response; WebSocket disconnect; duplicate delivery; concurrent workers; stale intent replay; database/ledger restart; partial reconciliation; and kill-switch activation during an in-flight operation. One logical intent must not create uncontrolled duplicate exposure.

## 11. Capital anomaly protection
If verified broker capital changes without a corresponding explainable ledger event, new exposure stops until resolved. Deposits, withdrawals, fees, bonuses, broker adjustments, and transfers must not be interpreted as trading P&L without explicit classification.

## 12. Economic evidence
Use net economics where measurable: net P&L = gross P&L − spread − commission − slippage − funding/holding costs − other applicable execution costs. COST_UNKNOWN or NET_EXPECTANCY=UNDETERMINED is not a positive economic result.

## 13. Research integrity
Research must preserve dataset lineage and prevent validation contamination. Prospective/OOS evidence must use data not used to develop or tune the evaluated strategy. Evidence must meet the existing Strategy × Symbol × Regime minimum-trade requirements.

## 14. Deployment provenance
The production worker must run the exact reviewed source commit and immutable configuration digest recorded by deployment evidence. A running service is not authoritative merely because it is running. The worker must be persistent, observable, restartable, and capable of producing the required audit trail.

## 15. Autonomous operation
Autonomy means no per-trade human approval is required after all gates are satisfied. It does not mean controls can be bypassed. Mandatory integrity failure prevents new exposure and initiates recovery. The kill switch remains independently available.

## 16. Prohibitions
Do not reconstruct missing historical source from summaries or documentation; deploy a substitute engine and represent it as recovered AURELIA; fabricate broker/OOS/calibration/economics/soak/deployment evidence; allow research agents to authorize capital; use stale/unverified balance as truth; blindly retry ambiguous broker outcomes; bypass Risk Warden, Execution Firewall, Capital Plane Gate, reconciliation, or kill switch; or silently rewrite production trading logic.

## 17. Release progression
SOURCE_RECOVERED → NATIVE_RUNTIME_VERIFIED → PERSISTENT_WORKER_VERIFIED → BROKER_LIFECYCLE_VERIFIED → RECOVERY/IDEMPOTENCY_VERIFIED → CAPITAL_RECONCILIATION_VERIFIED → PROSPECTIVE_RESEARCH_VERIFIED → CALIBRATION/ECONOMICS_VERIFIED → SECURITY/DEPLOYMENT_VERIFIED → CONTROLLED_CANARY → AUTONOMOUS_OPERATION.

A missing prerequisite remains UNKNOWN/blocked and is never inferred from another passing test.

## 18. Current boundary
The assurance repository can enforce and report these requirements, but the actual native runtime remains source-dependent. Until authoritative runtime source is recovered or explicitly designated as a new baseline, live execution remains blocked.