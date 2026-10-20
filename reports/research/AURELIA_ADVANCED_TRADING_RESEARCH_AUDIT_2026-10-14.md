# AURELIA Advanced Trading Research — Baseline Audit and Blocker Register

**Audit date:** 2026-10-14  
**Canonical repository:** https://github.com/Anto-30/aurelia-trading  
**Audited baseline:** `main` at `89ea6bb67443f2922b57ac61ea48fcf9bc9f00af`  
**Authority statement:** This document is an evidence-backed baseline, not a live release approval. Research findings, CI results, and public market-data collection do not grant capital authority.

## 1. Executive determination

**Overall status: BLOCKED for live execution; PARTIALLY VERIFIED for research and engineering.**

The canonical repository contains the expected single-engine architecture: strategy registry, deterministic authority/risk controls, release gate, Deriv session/adapter/lifecycle code, assurance workflows, and research modules. The checked-in release lock remains non-live (`FINAL_EXECUTION_AUTHORIZATION=false`, `LIVE_EXECUTION=BLOCKED`).

The most immediate policy defect on the audited `main` commit is a probability-policy mismatch: `runtime/core/authority.py`, `README.md`, `docs/AURELIA_STAKE_POLICY_2026-10-10.md`, and `scripts/production_acceptance_audit.py` still use a **0.50** minimum, while the approved project requirement is **0.55**. The upper bound is 0.75. PR #123 contains a candidate correction and regression tests but remains a draft and is not part of `main`.

A recent prospective R100 collection job completed successfully as a collector, but the strategy did not qualify: 688 observations, 518 out-of-sample observations, OOS win rate 50.386%, `QUALIFICATION_STATUS=ECONOMICS_FAILED`, and `EXECUTION_ECONOMICS=UNDETERMINED_PRODUCTION`. A successful collection is not a profitability result.

Authenticated Deriv validation is blocked because the protected production environment did not supply required authentication bindings in the inspected runs. The current adapter also lacks the source-bound, fresh, exact-contract broker-minimum-stake evidence object needed for safe live sizing. A non-production simulated 3,601-second certificate exists, but explicitly proves neither production runtime behavior nor a real Deriv lifecycle.

## 2. Evidence inventory

| Area | Status | Evidence and interpretation |
|---|---|---|
| Canonical repository and architecture | VERIFIED (source inspection) | Public repo and current `main` tree inspected. Research, strategy, adapter, authority, release-gate, test, workflow, and evidence directories exist. |
| Capital release lock | VERIFIED as blocked | `config/LIVE_LOCK.yaml` has `FINAL_EXECUTION_AUTHORIZATION: false` and `LIVE_EXECUTION: BLOCKED`. This is the correct safe state while qualification evidence is incomplete. |
| Probability interval on `main` | FAILED against the current requirement | Main authority and acceptance audit still expect 0.50–0.75, which is inconsistent with the 0.55–0.75 project policy. See Section 3. |
| Broker minimum-stake provenance | BLOCKED | `runtime/core/stake_sizing.py` can evaluate a numeric minimum, but a caller-supplied scalar does not establish broker source, freshness, account/currency binding, or exact-contract binding. The Deriv adapter does not yet emit the required evidence object. |
| Strategy registry | VERIFIED as not qualified | Nine registered candidates were inspected. `MSNR_LIQUIDITY_SWEEP`, `VWAP_PULLBACK_RECLAIM`, `OPENING_RANGE_BREAKOUT`, and `AUTONOMOUS_TICK_RETURN_SHOCK` are `RESEARCH_ONLY_UNQUALIFIED`; `S7_LRL_IFVG`, `S6_LIQUIDITY_SWEEP`, `S3_DONCHIAN_LWTI`, `CRT`, and `MICRO_SCALP_R100_TICK_MOM` are `BLOCKED_IMPLEMENTATION_NOT_VERIFIED`. All nine inspected entries show `calibration_status=NOT_RUN` and no qualification evidence IDs. |
| R100 prospective research collector | PARTIALLY VERIFIED; strategy failed qualification | Action run [38554782088](https://github.com/Anto-30/aurelia-trading/actions/runs/38554782088) reports 688 total and 518 OOS observations, OOS win rate 50.386%, `ECONOMICS_FAILED`, and production economics undetermined. |
| Authenticated Deriv session and verify-only lifecycle | BLOCKED | Action runs [38513482429](https://github.com/Anto-30/aurelia-trading/actions/runs/38513482429) and the authentication/lifecycle jobs in [38525889171](https://github.com/Anto-30/aurelia-trading/actions/runs/38525889171) failed closed because required protected Deriv secrets were absent. No secret values were accessed or logged in this audit. |
| Public Deriv feed reliability | PARTIALLY VERIFIED | An earlier R100 collection [38518579499](https://github.com/Anto-30/aurelia-trading/actions/runs/38518579499) failed on a WebSocket opening-handshake timeout; a later bounded-retry collection succeeded. Retryable collection failure must not be converted to positive strategy evidence. |
| Non-production soak | VERIFIED for its limited scope only | `reports/certification/SIMULATION_VERIFIED_NONPROD_3600S_2026-10-04.json` records 3,601 seconds, 706 health checks, three controlled restarts, zero health-check failures, and explicitly states no authenticated Deriv session, real transaction, capital movement, or live authorization. This is not a production soak. |
| Production host / production soak | UNVERIFIED / BLOCKED | The current operational-state document states that no owner-controlled production host handshake, deployment health check, real broker lifecycle, or production 3,600-second soak was verified. |
| Volume profile, CVD, depth/order flow | UNVERIFIED; disable unless source supports them | Public synthetic-index tick data is not proof of traded volume-at-price, aggressor-side classified volume, centralized depth, or participant identity. Do not synthesize these features from tick counts. |
| Competing exit backtests and ablations | NOT RUN / UNVERIFIED in this audit | The source tree includes deterministic research setup primitives, but this audit did not observe a reproducible, apples-to-apples comparative report using validated data, fill timing, quote costs, and OOS splits. No exit policy is endorsed. |
| Local tests / local working-tree diff | NOT RUN | This review used read-only GitHub source and workflow evidence. No claim is made that a local checkout, local formatter, type checker, or full local test suite was executed. Exact-head CI results are tracked separately on the draft PR. |

## 3. Highest-priority defect and safe remediation

### P0 — Probability policy drift

The inspected `main` source sets `MIN_PROBABILITY = 0.50`; README/stake-policy/acceptance audit also record 50–75%. This violates the prescribed inclusive **0.55–0.75** interval. Out-of-range values must be rejected, not clipped. Probability interval membership alone is insufficient: the signal must also be valid, fresh, calibrated, not drifted, qualified, and economically positive after realistic costs.

A candidate correction is held in [PR #123](https://github.com/Anto-30/aurelia-trading/pull/123), branch `fix/probability-broker-minimum-policy-2026-10-13`. It is intentionally still a draft. The branch now removes the separate $0.35 micro-capital helper, its tests, and its specification because the fixed stake would override the required 1%-risk affordability rule on small balances. The PR remains unmerged; do not treat its correction as effective on `main` until independent review and merge governance are complete.

### P0 — Broker minimum stake must be evidence, not an input

Normal sizing remains a deterministic risk-budget calculation, currently 1% of fresh, verified available USD balance rounded down to cents. If that budget cannot fund the fresh broker-reported minimum for the exact contract, trading must block. A numeric parameter passed by a strategy, agent, workflow input, or caller is not broker proof.

The current Deriv adapter must emit a source-bound evidence structure containing the observed broker minimum and contract parameters, receipt time/freshness, account identity, currency, source endpoint/response identity, and integrity binding. The deterministic authority must validate that structure before it can be used. Until this is implemented and adversarially tested, the draft branch fails LIVE authorization with `BROKER_MINIMUM_STAKE_EVIDENCE_NOT_IMPLEMENTED`; preserve that fail-closed behavior.

## 4. Prioritized blocker / remediation register

| Priority | Blocker | Required evidence to close | Current status |
|---|---|---|---|
| P0 | 50% vs 55% probability floor on `main` | Exact-head regression tests confirm 0.55 and 0.75 accepted, values just outside rejected, malformed/stale/uncalibrated/drifted values blocked; independent review and governed merge | FAILED on audited main; candidate fix remains draft |
| P0 | Protected Deriv credentials unavailable to inspected workflows | Configure secret *names/values* through authorized GitHub environment controls; run authenticated verification with no skipped auth steps; record redacted source-bound evidence | BLOCKED |
| P0 | Broker minimum is not source-bound | Exact-contract minimum evidence contract, adapter tests, negative tests for stale/mismatched account/currency/contract, caller-supplied scalars rejected | BLOCKED |
| P1 | Real verify-only lifecycle and reconciliation absent | Correct real-account identity/currency/balance, proposal/verify-only flow, broker transaction identifiers/status, idempotency, unknown-state resolution, and reconciliation evidence; zero capital movement during verification | BLOCKED |
| P1 | R100 economics do not qualify | Preserve frozen prospective OOS; collect valid exact-contract proposal/payout/cost observations; show positive mean net expectancy with uncertainty analysis, not only win rate | FAILED / undetermined production economics |
| P1 | Production runtime not independently verified | Authorized persistent host handshake and exact-commit deployment, runtime health/restart/persistence/recovery, source integrity and current attestations | BLOCKED |
| P1 | Production soak incomplete | A genuine 3,600-second run of the authoritative production-intended runtime with fault injection, event journal, heartbeats, restart recovery, and signed evidence bound to the exact source/runtime; non-production simulation is insufficient | UNVERIFIED |
| P1 | Strategy identities not qualified | Verify each implementation/registry binding, freeze parameters, validate data, run unit/integration and leakage checks, OOS/walk-forward/cost and calibration/drift gates, independent review | BLOCKED / NOT RUN |
| P2 | Exit policy and feature value unmeasured | Reproducible common-entry comparisons, cost-adjusted OOS, confidence intervals, regime/parameter sensitivity, ablations, and immutable experiment records | NOT RUN |
| P2 | Market microstructure feature support | Document actual vendor fields and granularity per instrument; otherwise disable volume profile, CVD, footprint, heatmap, and depth claims | UNVERIFIED for Deriv synthetic indices |
| P2 | Independent governance review | Independent reviewer inspects exact head, CI evidence, risk deltas, security/dependency results, and remaining scope; reviewer cannot authorise capital | No reviewer requested on PR #123 at audit time |

## 5. Research implementation specification — current disposition

| Research family | Deterministic comparison required | Current disposition |
|---|---|---|
| Exit policies | Use identical entry set and position sizing; compare fixed 1R/1.5R/2R/3R, break-even plus trailing, confirmed-pivot structure trailing, ATR/Chandelier, hybrid, partial exits, and time exits. Stops must never use future-confirmed pivots and must not loosen unless an explicitly tested policy requires it. Resolve intra-bar stop/target order with tick data or a conservative adverse assumption. Report net expectancy in R, PF, MAE/MFE, winner-to-loser reversal, giveback, drawdown/duration, tail losses, time in market, and regime stability. | NOT RUN; no evidence-based preferred exit. |
| Session ORB / displacement | Define session timezone/DST/holidays, exact first 5-minute range, close-confirmed breakout, 1-minute displacement/FVG, entry/stop/invalidation, retest/engulfing rule, duplicate-signal suppression, and fixed 2R benchmark vs 3R/trailing. For synthetic indices, first demonstrate a meaningful session or use a frozen rolling-range alternative. | Research-only ORB primitive exists; no qualifying transfer or comparative OOS report observed. |
| Market structure | Timestamp all 4H → 1H → 30M → 5M context where supported; separate approved 1-minute scalping. Confirm pivots only after their required bars; mechanically define BOS/CHOCH, consolidation, displacement, sweep, retest, and cash-flow-box open-and-close breakout. | Partial signal primitives exist; predictive value / leakage / OOS remain unverified. |
| Volume profile / CVD / order flow | Require true volume-at-price and defensible aggressor-side classification; state 70% value area algorithm; completed-session references only; separate executed trades from displayed liquidity. Compare base price action vs incremental features after cost. | Unverified for Deriv synthetic products; disable unavailable features, do not substitute tick counts as volume. |
| Value-area continuation/rejection | Freeze acceptance/rejection mathematically and test incremental value beyond trend, volatility, time, and recent returns; reject directional assumptions based solely on “premium/discount” labels. | Blocked until genuine volume-profile source and tested reference data exist. |
| ML / calibrated probabilities | Compare interpretable baselines first; feature availability timestamps; chronological train/validation/test; walk-forward plus purge/embargo where needed; calibration only on validation; untouched OOS; cost-adjusted strategy utility and ablation vs non-ML controls. | Research architecture documented, but qualification data and calibrated production model not evidenced. |
| R100 tick-momentum scalping | Capture earliest executable post-signal price, actual quoted contract payout/cost and latency, rejected proposals, maximum stake/loss constraints, and ambiguity in tick/bar event order. Assess block bootstrap and drawdown/losing streak risk. | 518 OOS observations present in latest collector summary; economics failed/undetermined, so not eligible. |

## 6. Research governance and test contract

For each candidate, freeze hypothesis, code/strategy version, dataset provenance and time range, timestamp/availability rules, entry/exit/sizing semantics, cost assumptions, sample size, trial count/OOS reuse, chronological split boundaries, model/calibration versions, and exact source commit. Save failed trials and parameter sensitivity results alongside successful ones. Keep Strategy × Symbol × Timeframe × Regime × Session × Exit Policy × Execution Environment separable and avoid treating differently named indicators as proof of portfolio diversification.

No universal win-rate threshold should substitute for net expectancy and uncertainty. For R100, 50.386% OOS win rate alone cannot establish profit or loss without the exact payoff and cost distribution; the collector’s own status is decisive here: economics failed / undetermined production.

The existing non-production soak artefact is useful limited control-path evidence but does not close any broker, production host, real lifecycle, OOS economics, calibration, or live release gate. Public market-data collection, a passing unit suite, static inspection, and green CI must remain separate from source-bound production qualification evidence.

## 7. Permitted next milestone

1. Keep `LIVE_LOCK` closed.
2. Complete independent review of draft PR #123 after the removal of the noncompliant micro-capital exception; verify the final exact-head CI and regression results before any merge decision.
3. Implement and adversarially test source-bound broker-minimum evidence without introducing another stake policy or authority.
4. Through authorized secret/host configuration, run verify-only Deriv auth and broker-read evidence, then transaction-lifecycle/reconciliation checks. Do not place a live order as part of verification.
5. Continue prospective OOS collection but do not retune on the campaign; capture exact quote economics and recalibrate only on permitted validation windows.
6. Verify the persistent production-intended runtime and its separate 3,600-second soak. Only after all evidence exists should independent reviewers reassess the release gate.

**Final determination:** AURELIA's fail-closed capital control is the right default, but it is not yet production-qualified. The next milestone is to repair the probability-policy drift, close broker-minimum evidence and authentication blockers, and obtain reproducible strategy economics—not to enable live execution.
