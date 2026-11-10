# 369/MSNR Research Verification Report

**Status:** RESEARCH_ONLY_UNQUALIFIED  
**Capital authority:** false  
**Execution authority:** false  
**Live execution:** BLOCKED  
**Report generated:** `NOT_RECORDED` until a reproducible run exists

## 1. Immutable run identity

| Field | Required value |
|---|---|
| Strategy ID / version | `THREE_SIXTY_NINE_MSNR / 0.1.0` |
| Source revision | Exact Git commit SHA |
| Strategy source SHA-256 | SHA-256 of implementation source |
| Simulator source SHA-256 | SHA-256 of simulator source |
| Configuration SHA-256 | SHA-256 of frozen config |
| Dataset SHA-256 | SHA-256 of immutable raw dataset |
| Cost-profile SHA-256 | SHA-256 of verified cost evidence |
| Runtime / dependency lock | Exact Python version and lockfile hash |
| Run command and environment | Reproducible command, OS, timezone |

## 2. Instrument and data qualification

Record separately for each symbol and timeframe: broker instrument identifier, instrument type, quote currency, price scale, tick size, contract specification, source, collection interval, timezone, bar-label semantics, expected cadence, missing/duplicate bars, maximum gap, freshness, and independent source verification.

**Unknown, stale, incomplete, or mismatched evidence means BLOCKED.** Do not impute bars, infer instrument mappings, or substitute synthetic values.

## 3. Frozen strategy variants

Report baseline, displacement, EMA/ATR extension, and each pre-registered ablation as separate variants. Include exact parameter values, signal-close rule, protected-swing source rule, stop buffer, 369 target-selection rule, and gross-R eligibility threshold. No post-hoc variant may be represented as pre-registered.

## 4. Execution and cost methodology

Document next-available-bar-open entry, gap-through-stop/target handling, stop-first resolution when both barriers are touched in an OHLC bar, no-fill/missing-bar handling, and explicit `END_OF_DATA` liquidation policy.

Provide verified, instrument-specific round-trip spread, incremental slippage (excluding spread), commission, other fees, and latency assumptions. Include evidence source, observation timestamp, sample count, units, return denominator, and freshness validation. Unknown costs block net-performance claims.

## 5. Performance results

Report per strategy × instrument × timeframe × regime cell:
- trade count and coverage;
- gross and net expectancy in R;
- profit factor;
- maximum drawdown and drawdown duration;
- R-multiple distribution and tail loss;
- win rate (descriptive only);
- itemized costs and cost sensitivity;
- confidence intervals and statistical uncertainty;
- adverse clustering / Monte Carlo results;
- Deflated Sharpe Ratio and number of trials;
- calibration metrics only when probabilities were trained and independently calibrated on chronological training data.

Do not aggregate across cells to conceal under-sampled or failing segments. Apply the current minimum-trade requirement per qualifying cell, not as a pooled total.

## 6. Out-of-sample and robustness

Record chronological train/validation/test boundaries, frozen parameters, embargo/purge rules where applicable, untouched sealed OOS identity, walk-forward windows, number of configurations tested, regime segmentation, sensitivity analysis, and independent replication. Any tuning after viewing sealed OOS results invalidates that OOS set.

## 7. Gate matrix

| Gate | Status | Evidence reference |
|---|---|---|
| Unit / simulator correctness | NOT_RUN until exact-head CI passes | |
| Dataset provenance and continuity | NOT_RUN | |
| Instrument mapping and tick precision | UNKNOWN | |
| Verified costs and latency | UNKNOWN | |
| Historical net economics | NOT_RUN | |
| Walk-forward validation | NOT_RUN | |
| Sealed out-of-sample | NOT_RUN | |
| Calibration | NOT_RUN | |
| Robustness / multiple-testing correction | NOT_RUN | |
| Forward paper evidence | NOT_RUN | |
| Runtime soak | NOT_RUN | |
| Independent review | NOT_RUN | |
| Strategy qualification | BLOCKED | |

## 8. Decision

**Default decision: REJECT FOR QUALIFICATION / CONTINUE RESEARCH ONLY** until every required evidence gate is independently satisfied. This report does not authorize capital, broker authentication, order submission, deployment, or modification of the canonical LIVE_LOCK.
