# AURELIA SMC Trend Research Validation Runbook

**Status:** Research-only. This runbook does not authorize strategy promotion, broker access, capital allocation, deployment, or order submission.

## Current research components

- Candidate detector: \`research/labs/smc_trend_agent.py\`
- Reference-level outcome evaluator: \`research/labs/smc_reference_evaluator.py\`
- Monthly split planner: \`research/labs/walk_forward_splits.py\`
- Detector tests: \`research/labs/tests/test_smc_trend_agent.py\`
- Outcome evaluator tests: \`research/labs/tests/test_smc_reference_evaluator.py\`
- Split planner tests: \`research/labs/tests/test_walk_forward_splits.py\`
- Strategy definition and parameter hypotheses: \`docs/SMC_TREND_AGENT_RESEARCH_SPEC_2026-10-14.md\`

The split planner creates boundaries; it does not load data or run a backtest. The evaluator produces OHLC reference outcomes; it does not simulate executable orders or broker P&L. Do not describe either as a completed performance study.

## 1. Freeze the data before testing

For each dataset, preserve a manifest with:
- source/provider and retrieval timestamp;
- account/instrument identifier and exact contract type;
- timeframe and timezone convention;
- first and last bar close timestamps;
- row count, duplicate count, missing-interval count and OHLC validation result;
- raw file SHA-256, normalization version, and any corporate-action/session adjustments;
- instrument tick size, payout/payoff schedule, minimum stake, fees, spread, slippage and settlement/expiry semantics, all with source evidence.

Keep original raw data immutable. Normalize into completed, timezone-aware OHLC bars with strictly increasing close timestamps. Reject duplicates, malformed OHLC geometry, non-finite values, non-positive prices where inappropriate, unexplained gaps, and any row whose close time exceeds the evaluation cutoff. Never silently fill missing bars. Treat Deriv tick-arrival counts as tick observations, not traded volume or order-book depth.

## 2. Define and seal the experiment

Before examining OOS results, version and hash:
- strategy source and parameters;
- symbols/contracts and session filters;
- dataset manifest and train/OOS boundaries;
- entry-reference, invalidation, expiry, stop/target reference and ambiguous-bar rules;
- costs and contract payoff mapping;
- primary metric, minimum sample size and promotion/rejection thresholds.

Use \`monthly_walk_forward_splits(..., in_sample_months=3, out_of_sample_months=1, step_months=1, purge_days=N)\` to create a rolling plan. Select \`N\` from the maximum label horizon/holding period and any overlapping feature/label window; do not choose it to improve results. Ensure OOS windows do not overlap. Confirm the dataset fully covers each requested window before evaluating it.

All fitting, threshold selection, feature normalization, filtering and calibration must use only the training interval. Purge observations must be excluded from both training and scoring. Do not retune on a failed OOS month and then continue to call that month OOS.

## 3. Evaluate reference paths conservatively

Run the candidate detector only on information available at each signal close. Feed the evaluator only later bars. A price touching the entry reference is not proof of a fill. For OHLC bars where intrabar ordering is unknowable, preserve the evaluator's ambiguity label and do not count the event as a clean win. Report separately:
- valid candidates;
- pending-at-end and expired candidates;
- invalidated-before-entry candidates;
- ambiguous entry/exit bars;
- stop and target reference outcomes;
- unresolved/open outcomes.

Do not compute a profitability claim by dropping ambiguous or unresolved cases without a pre-registered policy. Do not convert reference R into contract return without a verified contract/payoff mapping.

## 4. Required performance and robustness report

At minimum, report per symbol, contract, session, direction and OOS fold:
- number of signals and resolved outcomes;
- gross reference expectancy in R, with unresolved/ambiguous counts shown;
- win rate and its confidence interval;
- profit factor only where gross gains/losses are defined and denominator is non-zero;
- maximum drawdown from a correctly ordered equity series;
- exposure/time-in-market and holding-time distribution;
- turnover, spread, fees, slippage, rejected/failed fills and all contract-specific payout costs;
- net expectancy and drawdown only after the cost and contract mapping has been independently verified;
- parameter sensitivity, nearby-threshold stability, adverse-regime performance and a multiple-testing/selection-bias assessment.

Keep fold-level results. Do not rely on one aggregate metric or the best-performing parameter set. A positive result is not qualified until sample size, uncertainty, data quality and costs are acceptable under pre-registered criteria.

## 5. Prospective OOS and operational gates

After historical protocol and parameters are frozen, run a prospective data-collection period with timestamped, append-only evidence. Record data gaps, detector version/hash, each candidate including rejected candidates, and the exact reason for every outcome. Do not silently repair the dataset or change strategy parameters during the sealed period.

Before any promotion request, require:
1. independent review of implementation and experiment design;
2. reproducible historical and rolling OOS results;
3. verified instrument-specific cost/payoff mapping;
4. prospective OOS with adequate sample size and no unlogged intervention;
5. calibration/stability review where probabilistic scores are used;
6. authenticated read-only broker/account evidence and verify-only lifecycle evidence;
7. risk-owner approval, current readiness evidence and all existing AURELIA release gates.

If any prerequisite is missing, stale, inconsistent or unknown, mark the result unqualified and fail closed. Never weaken \`LIVE_LOCK\`, bypass the canonical risk engine, or use research-agent output as capital authority.

## Current blocker statement

As of the research branch's documented assurance run, software tests and public market-data transport passed, but authenticated real-account session verification, broker-derived account evidence, verify-only transaction lifecycle, historical SMC performance, cost-adjusted OOS results, prospective OOS qualification and independent human review were not established. This runbook documents the path to generate those artifacts; it does not claim they exist.
