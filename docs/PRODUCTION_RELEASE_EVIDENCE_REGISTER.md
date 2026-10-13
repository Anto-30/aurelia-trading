# AURELIA Production Release Evidence Register

**Status as of 2026-10-14: NOT READY — VERIFY_ONLY.**  
Canonical repository: `Anto-30/aurelia-trading`. This register is a release checklist, not evidence that a gate has passed. Evidence must be current, attributable to the exact release commit, independently inspectable, and retained without secrets.

## Non-negotiable controls

- `config/LIVE_LOCK.yaml` remains the authority for live release. Current main-branch values are `live_trading_enabled: false`, `FINAL_EXECUTION_AUTHORIZATION: false`, `LIVE_EXECUTION: BLOCKED`, and `capital_plane_mode: VERIFY_ONLY`.
- Research agents, third-party repositories, CI jobs, and deployment tooling must not change the capital plane, unlock live execution, or submit an order.
- Never place Deriv tokens, OAuth secrets, private keys, or credential-bearing URLs in this register, GitHub comments, logs, or artifacts.
- Unknown broker outcomes must block further submissions until transaction/contract lookup and reconciliation resolve them. No blind resubmission.

## Release gates and evidence required

| Gate | Current assessment | Required evidence to close |
|---|---|---|
| Exact source / CI | CI has previously passed tests on a PR head; re-check exact head before release | Commit SHA; all required workflow runs and jobs; test, dependency, and security reports attached to that SHA |
| Independent review | No independent approval confirmed in current review snapshot | Approval from a qualified reviewer who did not author the change; review must cover changed files and risk boundaries |
| Deriv authentication / identity | Not verified against a live authenticated session in this engineering session | Redacted session verification record showing authenticated status, expected login ID match, account type, currency, environment, timestamp, and source commit; never include token |
| Broker stake/contract evidence | **BLOCKED**: authority gate explicitly returns `BROKER_MINIMUM_STAKE_EVIDENCE_NOT_IMPLEMENTED` for LIVE | Typed, immutable, source-bound evidence from the adapter; must bind account/login ID, environment, currency, exact symbol/contract type, stake basis and amount, proposal/quote ID, broker response digest, capture time, expiry/freshness, and request correlation ID. Reject mismatches, missing fields, stale evidence, replay, and caller-supplied scalar-only values. Do not infer a general minimum from one accepted quote. |
| Verify-only broker lifecycle | Not verified against a real broker lifecycle in this session | Authenticated proposal/quote → verify-only intent → broker read-only lifecycle evidence; no capital-moving buy; correlate request and response IDs |
| Transaction / contract reconciliation | Not proven for a real broker transaction lifecycle | Broker statement/transaction and portfolio/open-contract views reconcile to the same known event; demonstrate UNKNOWN handling, idempotency, and no blind resubmission using controlled tests |
| Strategy out-of-sample qualification | Incomplete / no qualifying evidence confirmed | Frozen strategy and data hashes; separated train/validation/OOS windows; sufficient multi-day and regime coverage; no leakage; sample-size and confidence intervals; independent reproducibility |
| Probability calibration and drift | Incomplete / no qualifying evidence confirmed | Versioned calibration dataset and method, Brier/log-loss/reliability results, freshness bounds, drift test and thresholds; stale, uncalibrated or drifted predictions rejected |
| Net economics | Incomplete / no qualifying evidence confirmed | Contract-specific payout and stake basis, fees/spread/slippage/quote costs, expected value after costs, uncertainty and sensitivity analysis; reject COST_UNKNOWN and non-positive net expectancy |
| 3,600-second soak | Not evidenced | Timestamped uninterrupted run from the exact deployed image/commit; heartbeats, process restarts, queue/lease health, data freshness, circuit-breaker and kill-switch tests; captured logs/metrics and explicit failure accounting |
| Production runtime / host | Not verified; current operational note says no user-controlled host handshake was performed in that session | Exact-commit deployment receipt, strict host-key verification, immutable release ID, image digest, service health, persistent state verification, restart/recovery proof and host-side telemetry. No credentials in artifacts |
| Security / secret exposure | A prior Drive audit reported 225 files shared “Anyone with the link”; credential/configuration exposure requires owner-side remediation and re-check | Remove inappropriate public sharing using the Drive owner UI/tool; inspect access and audit logs; assess credential rotation under owner approval; repeat scan and retain before/after counts without publishing secrets |
| Final release authority | **BLOCKED** | All preceding evidence gates pass; independent review; exact commit and config digest match; deterministic gate output; explicit owner approval. Do not change LIVE_LOCK before this point |

## Source-bound broker evidence contract

A scalar `broker_minimum_stake: float` is not evidence. The adapter must create the evidence object directly from a validated broker response, not from strategy input or caller-provided values. Authority must verify provenance, freshness, account/environment/currency binding, exact contract and amount/basis binding, correlation/replay protection, and requested stake affordability against fresh available capital. The object must be immutable and must not be accepted if constructed from untrusted payload data. Add adversarial tests for stale timestamps, future timestamps, wrong account, wrong currency, wrong environment, wrong symbol, wrong contract type, wrong basis, altered amount, missing proposal ID, response/request correlation mismatch, replay, malformed/non-finite values, and broker rejection.

The exact Deriv API response fields and semantics must be verified against the current official API contract before implementing this adapter. A proposal accepted for one amount does **not** establish a universal broker minimum. The evidence should describe the exact quote/request and only support the decision it actually proves.

## External agent/repository policy

Claude Code, Hermes Agent, OpenClaw, and other external repositories may be used for isolated research, code review, test generation, and patch proposals only. They are not installed or executed by this register and are not release authorities. Pin reviewed upstream commits/releases, inspect dependency and license/security posture, and run third-party code in a sandbox with no Deriv credentials, no production network, and no capital-plane permissions. Merge contributions only through this canonical repository and its existing PR/review/CI process.

## Current disposition

Do not merge PR #123, mark it ready, deploy it as production-qualified, or enable live execution based on this register. The register remains NOT READY until every applicable gate has its own retained evidence and independent verification.
