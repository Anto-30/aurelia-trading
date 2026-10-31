# Senchi Weekly Profile Research (Research-Only)

## Status

This is an experimental higher-timeframe context study. It is not a trading strategy release, does not create an execution signal, and cannot authorize capital movement. T4F × 369 M15/M1 execution is a separate validation stage and is not represented by the daily-bar outcome statistics.

## Frozen v0.1.0 definitions

- Instrument identity is explicit in the run command (for example, R_100). Do not merge symbols or account types into one sample.
- Input consists only of complete 1D OHLC candles with UTC-midnight timestamps and columns timestamp_utc,open,high,low,close.
- The objective external range is the previous completed Monday–Sunday UTC calendar week. Both PWH and PWL are aggregated from those seven daily bars. An incomplete prior week is not used.
- Monday is a reversal only when its high strictly exceeds PWH or its low strictly breaches PWL and its close finishes inside the inclusive PWL–PWH range.
- A Monday close above PWH or below PWL is an expansion and overrides a wick sweep of the opposite boundary.
- A Monday candle sweeping both boundaries and closing back inside is classified COMPLEX_DUAL_SWEEP; it is not assigned a directional bias.
- An inside day neither sweeps either boundary nor closes outside it.
- Tuesday's target is the opposing prior-week boundary. Its invalidation is the Monday reversal candle's extreme.
- If Tuesday daily OHLC touches both target and invalidation, the order of events cannot be known from daily bars; the observation is classified ambiguous rather than a win or loss.
- An opening gap through the target or invalidation is separately labelled. Target-at-open counts as target already reached for the HTF hypothesis, but does not imply a tradable entry existed at Tuesday's open.

## Calendar caveat

The UTC Monday–Sunday week is an objective proxy for an ICT/Senchi weekly profile. It is not interchangeable with a New York-close daily candle or a Sunday-evening futures week. A separate, properly aggregated New York-close experiment is required before making claims about that variant. Do not relabel UTC candles as New York-close bars.

## Input validation

The engine rejects empty inputs, naive timestamps, non-midnight daily candle boundaries, duplicate timestamps, non-chronological data, missing daily intervals, non-finite/non-positive prices and invalid OHLC relationships. For a 24/7 synthetic index, a missing daily candle is treated as a data-integrity failure, not as a market holiday to silently skip.

## Run

Run the regression suite with:

    python -m unittest research.labs.tests.test_senchi_weekly_profile -v

Run the research command with:

    python -m research.labs.senchi_weekly_profile --input data/deriv/R_100_1D_UTC.csv --output reports/senchi_R_100_1D_research.json --symbol R_100 --source "Deriv public market-data WebSocket; ticks_history candles; granularity=86400"

The CSV must contain timestamp_utc,open,high,low,close. Preserve the raw API response separately and record its SHA-256, request parameters, symbol, requested interval, returned interval, capture timestamp, and source commit. Never fill missing bars with interpolation or synthetic data.

## Interpretation gates

1. First validate that the downloaded candles exactly cover the declared period with no duplicates, gaps, or out-of-range rows.
2. Report all Monday action categories, not only reversals, to expose selection frequency.
3. Report target-touch rate across all reversal signals separately from decisive target-first versus stop-first outcomes.
4. Keep same-day target/stop double-touches, no-hit cases and missing-Tuesday cases visible. Do not remove them from the all-setups denominator.
5. Daily OHLC target reach is not an executable return. The T4F × 369 stage requires chronological M15/M1 data, fully deterministic liquidity-sweep/MSS/displacement/FVG rules, realistic fill assumptions, and instrument-specific spread/slippage/fees.
6. Reserve a chronological out-of-sample period and do not tune thresholds on it. Compare against unconditional Tuesday target-touch and matched non-reversal baselines. Use confidence intervals and dependence-aware resampling by week; a simple win-rate threshold is not sufficient evidence of edge.

## Historical data retrieval result — 2026-10-31

R_100 was confirmed active on the Deriv public WebSocket market-data endpoint. The initial single-window request and a follow-up partition into eight contiguous, non-overlapping intervals both failed historical range validation.

All eight chunk requests echoed their requested symbol, start, end, style, granularity and request ID, but each returned the same 366-row block dated 2025-10-31 10:06:12/13 UTC through 2026-10-31 00:00:00 UTC. Across 2,928 returned rows, all 732 requested UTC dates from 2022-10-21 through 2024-10-21 were missing and all 2,928 rows were outside the requested interval. The repeated block produced 2,561 duplicate timestamp occurrences and 2,562 duplicate UTC-date occurrences. OHLC numeric sanity checks passed for the returned rows, but that does not repair the date-range mismatch.

The normalized response hash is 8817ac28862e29b19fda059acb300ceb4e5bbbac005d95df0fed9e04f088e597. The full request partition, echo checks, duplicate counts, normalization definition and hash are archived at reports/research/SENCHI_R100_HISTORY_VALIDATION_2026-10-31.json.

Result: REJECTED_RANGE_MISMATCH. No performance statistic or backtest result was calculated from this response. Do not substitute the repeated latest-year block for the requested 2022–2024 sample. Historical access must be resolved with Deriv before this strategy hypothesis can be empirically evaluated.

## Governance

The module declares RESEARCH_ONLY=True, CAPITAL_AUTHORITY=False, and LIVE_EXECUTION=False. It returns trade_signal=False and execution_authorized=False. It is not imported by the broker executor, capital plane, or runtime strategy dispatch. The existing config/LIVE_LOCK.yaml remains authoritative and unchanged.
