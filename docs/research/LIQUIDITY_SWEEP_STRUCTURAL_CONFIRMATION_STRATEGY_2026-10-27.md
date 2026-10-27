# Liquidity Sweep + Structural Confirmation Strategy (Research Only)

**Status:** PROPOSED / NOT VALIDATED  
**Date:** 2026-10-27  
**Scope:** Deriv synthetic indices; initial candidate R_100, 1-minute setup with completed 15-minute context  
**Authority:** Research only. No broker execution permission is granted by this specification.

## Safety invariants

- Preserve `config/LIVE_LOCK.yaml`; do not modify it as part of strategy research.
- No live orders, live credentials, broker transaction calls, or capital authorization are needed for this work.
- Missing, stale, inconsistent, or unversioned inputs yield `ABORT` / `VERIFY_ONLY`.
- Agents and external repositories are advisory. They cannot authorize capital, alter risk controls, or bypass the execution firewall.
- A passing backtest is not live authorization.

## Hypothesis

A confirmed sweep of a previously defined swing level followed by a close back inside the prior range and a subsequent structural break may identify short-horizon mean reversion / expansion opportunities. This is a hypothesis to falsify, not an established edge. Synthetic-index price behavior must be tested from instrument-specific observed data; do not infer a real order book, resting orders, traded volume, CVD, or maker/taker fees.

## Deterministic candidate rules

### Inputs
- Timestamped OHLC or tick-derived candles from a documented, authorized source.
- UTC timestamps, explicit instrument identifier, timeframe, dataset hash/version, and source metadata.
- Completed candles only for all signal features.
- Quote/contract economics and applicable costs captured at decision time for any simulation.

### Context
1. Calculate swing highs/lows with a fixed, versioned pivot rule. A pivot is not available until the required right-side confirmation candles have completed.
2. The current prototype requires a separate, already-resampled 15-minute OHLC series. It does not infer or fabricate a 15-minute series from the 1-minute series.
3. A 1-minute candidate is retained only when the last two confirmed 15-minute swing highs and lows both rise for a long candidate or both fall for a short candidate. Mixed/insufficient context is neutral and rejects the candidate.
4. Only 15-minute candles with close timestamps strictly earlier than the 1-minute confirmation candle are eligible. A context candle timestamp equal to or after the confirmation time is excluded.
5. Both series must have strictly increasing, timezone-aware ISO-8601 timestamps representing candle-close times. Do not change swing definitions, context windows, or thresholds after viewing the sealed out-of-sample period.

### Long candidate
1. Price crosses below a previously confirmed swing low.
2. A completed candle closes back above that swing low within the pre-registered maximum number of bars.
3. After the reclaim, a completed candle closes above a previously confirmed local swing high (structural confirmation).
4. Enter only at the next eligible observed quote after confirmation, using a realistic execution model.
5. Place the stop beyond the sweep extreme plus a fixed buffer defined in advance.
6. Set target using a separately registered reward:risk variant (1:2 or 1:3). Do not optimize these variants on the sealed OOS set.

### Short candidate
Apply the exact mirrored conditions: sweep above a confirmed swing high, close back below it, then close below a confirmed local swing low. Stop beyond the sweep extreme plus the preregistered buffer.

### Rejections
Reject when inputs are stale or incomplete; a pivot is not confirmed; spread/cost inputs are unavailable where required; the entry quote is unavailable; the stop distance is zero/invalid; the required stake cannot be afforded under existing policy; the signal is duplicated; or the probability/calibration/regime gate required by the deployed governance policy is not satisfied. Never force a stake or override canonical risk sizing.

## Current implementation notes

- `research/labs/liquidity_sweep_strategy.py` emits research candidates only and requires caller-supplied 15-minute context.
- `research/labs/liquidity_sweep_controls.py` tracks expiring candidate setups and rejects future-dated/invalid state. It is not an order manager.
- `research/labs/liquidity_sweep_backtest.py` uses explicitly supplied fixed quantity, commission-per-side and adverse-slippage basis points. It is a deterministic OHLC approximation, not a broker fill simulator. When stop and target are both touched within a candle, stop is counted first; a stop gapped through is filled at the worse candle open. These assumptions can be pessimistic and do not resolve intrabar path uncertainty.
- Walk-forward folds use distinct chronological train/test windows. The callback must fit/calibrate from train bars and produce signals indexed locally to the test fold. A successful run does not establish edge without a frozen, source-verified dataset, suitable costs, sufficient sample size, sealed OOS and independent reproduction.
- Runtime dependencies remain standard-library only for these research modules; pandas/NumPy are not required.

## Experiment plan

1. Freeze this specification and version the implementation before running the primary experiment.
2. Establish simple baselines (no-trade, naive directional, and a simple swing-break baseline where appropriate).
3. Split chronologically into development, validation, and sealed out-of-sample periods; use walk-forward folds and preserve a final untouched period.
4. Include only defensible instrument-specific costs and execution constraints. If costs cannot be measured, report sensitivity scenarios and mark economic validity unresolved.
5. Record every candidate signal and every rejection, not only filled or winning trades.
6. Report trade count, net expectancy per trade, profit factor, win rate, average win/loss, maximum drawdown, exposure/time-in-market, turnover, costs, confidence intervals where appropriate, and results by fold/regime.
7. Perform parameter sensitivity and ablation tests; correct for repeated strategy trials and selection bias.
8. Run prospective paper/verify-only observation after historical checks. Reconcile intended signal, quote, simulated fill, exit, and ledger record.
9. Require independent review and all existing release gates before any promotion. Live trading remains blocked unless a separate authorized process changes the release state.

## Agent workflow (advisory only)

- Orchestrator: assigns bounded tasks and records evidence lineage.
- Research: proposes falsifiable hypotheses and documents assumptions.
- Quant: implements deterministic features and baseline comparisons.
- Challenger: searches for counterexamples, leakage, and simpler explanations.
- Validator: independently reproduces OOS and cost-adjusted results.
- Execution analyst: validates quote availability and simulated fill assumptions without sending orders.
- Auditor: verifies hashes, test output, policy invariants, and report consistency.
- Canonical risk/release authority: existing AURELIA components only; no LLM or agent gets capital authority.

Parallel agents may review independently, but conclusions are merged only through deterministic evidence checks. A majority vote is not evidence.

## Required artifact schema

Each experiment record should include:
- strategy_id and immutable strategy_version
- git_commit, dataset_hash, dataset_version, source, instrument, timeframe
- UTC start/end and split boundaries
- parameters and cost-model version
- command/environment/dependency versions
- signal/trade ledger and rejection ledger
- metrics, uncertainty estimates, warnings, and test logs
- independent reviewer outcome
- final status: `REJECTED`, `INCONCLUSIVE`, or `RESEARCH_PASS`

## Promotion criteria

A `RESEARCH_PASS` requires reproducible results, no known lookahead/leakage, positive net expectancy after defensible costs across the preregistered OOS evaluation, acceptable drawdown under existing policy, robustness to reasonable parameter variation, and independent review. Failure or unknown status on any mandatory gate blocks promotion. This status never equals live execution authorization.
