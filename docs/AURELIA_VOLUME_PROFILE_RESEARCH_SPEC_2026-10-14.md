# AURELIA Volume Profile / MSNR Research Specification

**Status:** research-only prototype and specification. This is not strategy qualification, production market-data integration, or live-execution authorization.

## 1. Scope and authority

The prototype at research/labs/volume_profile_proxy.py counts observed tick records per price bin. It is not traded contract volume, notional turnover, bid/ask volume, order-book depth, or proof of institutional participation. It carries RESEARCH_ONLY=true, CAPITAL_AUTHORITY=false, and LIVE_EXECUTION=false. It adds no broker transport or order submission. Do not create a second engine, attach the feature to the executor, change config/LIVE_LOCK.yaml, or bypass Layer 6 and the capital plane.

## 2. Provider and data semantics

AURELIA's canonical production Options path is api.derivws.com. The existing repository policy marks ws.derivws.com / Binary WS v3 as diagnostic-only, never a production fallback. This prototype accepts already-collected {price, epoch} rows and deliberately does not fetch data. First verify the current public market-data schema and supported endpoint with Deriv documentation and the existing runtime adapter before adding an ingest adapter. Any legacy endpoint experiment must remain isolated and visibly tagged as diagnostic-only. Do not put a token in passthrough metadata; it is not authentication and may be echoed.

Every data sample must retain instrument/symbol, source and endpoint version, request and observation interval, collection time, epoch units, row count, duplicate/gap checks, data hash/version, and the explicit tick-activity-proxy declaration. Missing interval coverage, stale data, unknown timestamps, malformed values, or unverified source must yield UNVERIFIED and prevent signal qualification.

## 3. Profile contract

- Calculate separate configured daily/weekly, confirmed-swing fixed-range, 15-minute-context, and 1-minute execution profiles. Do not mix their windows.
- Do not assume a Sunday close for 24/7 synthetic indices. Use an instrument schedule and a fixed UTC anchor; a Monday 00:00 UTC weekly boundary may be tested if pre-registered. FX/venue-linked instruments require explicit session and daylight-saving rules.
- Use only swings confirmed by the decision timestamp. Swing confirmation delay belongs in the strategy and replay; no future-confirmed anchor may leak into prior profiles.
- Prefer an instrument-calibrated fixed bin width for comparisons. Equal-width bins based on each sample's own range are exploratory and make levels range-dependent. Record window, binning method/width, tie policy, and config hash.
- POC ties use a deterministic documented rule. The default 70% value area expands outwards from POC; report both the requested and actual fraction, total tick count, every bin count, and VA boundary convention.
- The included HVN/LVN detector returns only candidates using a version-labelled adjacent-bin heuristic. It operates on tick counts, not true volume. Threshold sensitivity and OOS stability are required before a strategy may rely on those labels.
- At time t, profile inputs must use only observations timestamped at or before t. 1-minute profiles are sparse/noisy; require pre-registered 15-minute context and any configured higher-timeframe narrative.

## 4. Separate MSNR hypotheses

1. VAH/VAL rejection: require a tested boundary, pre-defined rejection criteria, confirmed MSNR structure shift, higher-timeframe alignment, acceptable costs, and a feasible outcome model. A wick alone is insufficient.
2. Acceptance/breakout: require a completed candle outside VA, pre-registered persistence/acceptance criteria, and a defined retest/continuation rule. Distinguish close-through from wick-through.
3. HVN rejection: a candidate only when the versioned node detector and confirmed MSNR agree. Do not call it high-conviction before OOS evidence supports that label.
4. LVN continuation: a separate momentum hypothesis, not a reversal fade. Default-block reversal fades inside LVNs; do not enable LVN continuation merely because price enters a low-count bin.
5. POC interaction: classify test, rejection, or acceptance using pre-registered rules. Do not assume POC is always magnetic.

Any 50% size reduction in LVN space is subordinate to the existing deterministic stake/risk rules. If a reduced size falls below the broker minimum, reject rather than round up above the risk budget. A spread threshold must be instrument-specific, verified, and have explicit units; never substitute generic pips for synthetic-index points or infer a spread if the product/feed does not expose it.

## 5. Layer 6 proposed vetoes (not active in this PR)

Layer 6 must consume normalized facts and return deterministic allow/reject reasons, not ask an LLM to authorize risk. Suggested fail-closed conditions:

- PROFILE_DATA_STALE, PROFILE_WINDOW_INCOMPLETE, PROFILE_BINNING_UNVERIFIED, NODE_POLICY_UNQUALIFIED, or TICK_ACTIVITY_SOURCE_UNVERIFIED.
- COST_PROFILE_UNKNOWN, required spread unavailable, excessive verified cost, or latency/slippage outside the qualified envelope.
- MSNR/profile disagreement or unconfirmed 15-minute context.
- A completed 15-minute bar outside VA against an open position with tick-activity count above a matched-window baseline may raise an alert or veto new entries. Call this a 2x tick-activity condition, never 2x volume. Do not liquidate unless existing Layer 6 rules and contract lifecycle support it.
- Unsupported stop semantics or missing node detector => no invented stop/target. Purchased fixed-payout contracts must be evaluated in contract P&L/payout space; an underlying-price stop is not automatically realizable.

This research package must never generate an order object, stake, execution authorization, or live-lock update.

## 6. Backtest and qualification

1. Freeze symbols, profile windows, session boundaries, bin width, VA fraction, swing confirmation, MSNR definitions, node thresholds, filters, costs, and outcome logic before the final holdout.
2. Replay profiles point-in-time. Test gaps, duplicate/late/out-of-order ticks, time-zone conversion, reconnect gaps, and session completeness. Never forward-fill activity over missing data.
3. Use chronological train/validation/OOS, walk-forward tests, purging for overlapping trades where needed, and a sealed prospective OOS stream. Reuse AURELIA's existing validation, cost-model, evidence, and strategy governance.
4. Segment metrics by INSIDE_VALUE_AREA, ABOVE_VAH, BELOW_VAL, HVN_REJECTION_CANDIDATE, LVN_CONTINUATION_CANDIDATE, strategy, symbol, session, and regime. Compare with MSNR-only and no-profile baselines to test incremental value.
5. Report sample size, gross and cost-adjusted expectancy, R distribution, profit factor, win rate with uncertainty, maximum drawdown, loss streaks, trade frequency, OOS fold/regime stability, and excursion metrics if supported. PF is undefined if gross loss is zero; do not call it infinite evidence. Unknown costs remain UNKNOWN, never zero.
6. For Deriv fixed-payout/purchased contracts, outcomes must be computed from actual contract payout and stake economics. Underlying-price return is not realized strategy P&L. Do not invent spread, slippage, fills, volume, or order-book data.
7. Compare with CME 6E only for a suitably matched FX research question with synchronized data and documented basis. CME futures are not a valid volume benchmark for Deriv synthetic indices. Correlation with volatility is descriptive, not causal proof or trade qualification.
8. PF above 1.3, if used as AURELIA's research screen, is only a screening pass. Also require positive cost-adjusted OOS expectancy, adequate sample size, cross-fold/regime stability, prospective OOS, risk review, and existing release gates. Never tune to final OOS results.

## 7. Copy/paste prompt for Layer 9 Research Engine

> **Role and boundary:** Act as AURELIA Layer 9's quantitative research analyst. Analyze Volume Profile / tick-activity context for 1-minute execution hypotheses, 15-minute structure, and MSNR confluence. You are advisory-only: no capital authority, broker execution, risk-limit changes, strategy promotion, or permission to change config/LIVE_LOCK.yaml.
>
> **Data first:** State instrument/contract type, source/version, timezone, profile interval, observed tick count, freshness, gaps/duplicates, binning method/width, and whether input is actual traded volume or tick activity. Unless the exact source proves traded-volume quantity, label Deriv observations TICK_ACTIVITY_PROXY. Never infer institutional flow, order-book depth, delta, or buyer/seller volume from it. Missing lineage, incomplete windows, unknown costs, or missing node configuration => UNVERIFIED; do not estimate performance.
>
> **Profiles:** Calculate separate daily/weekly, confirmed-swing FRVP, 15-minute context, and 1-minute execution profiles. Return POC, VAH, VAL, requested/actual value-area fraction, bin width, tie rule, window timestamps, and node candidates with detector version/thresholds. Use only data at or before the decision timestamp and do not use future-confirmed swings.
>
> **Narrative:** Classify relation to VA as INSIDE_VALUE_AREA, ABOVE_VAH, or BELOW_VAL. Classify boundary/POC interactions as test, rejection, or acceptance only if pre-registered rules pass. Check higher-timeframe structure and confirmed MSNR BOS/CHoCH before discussing 1-minute setups. Separate VAH/VAL reversion, acceptance/breakout, HVN-rejection candidate, and LVN-continuation candidate. A wick, POC touch, or node label is not an entry. Default-block reversal fades within LVNs; test LVN continuation separately.
>
> **Execution levels:** Give entry/stop/target only when real input, instrument tick size, contract mechanics, and outcome model support them. Include the exact trigger timestamp/rule. Do not invent levels. For purchased fixed-payout contracts, describe risk in contract payout/P&L terms rather than claiming an underlying price stop is executable. Missing inputs => NOT_AVAILABLE.
>
> **Layer 6:** Return proposed veto reasons, never an authorization. Flag stale data, incomplete profiles, unqualified node rules, unknown costs/spread, excessive costs/latency, missing 15-minute context, weak MSNR confirmation, and absent OOS qualification. If a 2x activity condition applies, state the matched baseline/window and call it TICK_ACTIVITY_COUNT. Any 50% LVN size proposal is subordinate to risk limits and minimum stake; if both cannot be satisfied, reject. Do not compute a live stake or submit an order.
>
> **Evidence:** Only report metrics actually computed from versioned data. Include sample size, gross/net expectancy in consistent units, R distribution, profit factor, win rate with uncertainty, max drawdown, loss streak, session/regime splits, and walk-forward/OOS results. Compare HVN rejection and LVN continuation separately against MSNR-only. No valid historical results => win rate/profit factor NOT_ESTIMATED. Unknown cost => UNKNOWN, not zero.
>
> **Output:** Produce structured JSON with data_status, profile_kind, profile_window, binning_config, poc, vah, val, node_candidates, htf_context, msnr_state, setup_class, entry, stop, target, estimated_r, historical_metrics, layer6_vetoes, limitations, oos_evidence_ref, and trade_signal. trade_signal must be false whenever data or qualification gates fail. This payload never authorizes capital.

## 8. Acceptance gates

- Unit tests cover empty/malformed/non-finite data, flat-price samples, POC at a boundary, zero-count gaps, reproducible fixed-width bins, tie handling, value-area fraction, and price-context labels.
- Compare levels against an independent implementation using the same declared tie semantics.
- Prefix-stability test proves appending future ticks cannot change a closed profile at time t.
- Verify a stable, current Deriv public data adapter; do not route production through legacy V3.
- Sensitivity-test bin width, VA fraction, node detector, session anchor, and MSNR swing confirmation.
- Verify the product-specific cost/payout model. Unknown required costs block qualification.
- Keep independent review, OOS evidence, deployment/runtime verification, soak, and all existing AURELIA release gates independent from these research tests.
