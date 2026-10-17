# Deriv order-flow proxies and event-conditioned labels

Status: research-only, pending review and data validation. This design does not qualify a strategy or authorize an order.

## 1. Source-data boundary

The current public Deriv documentation describes historical tick data under history.prices and history.times; it does not document a historical traded-volume array in that response. The live tick schema guarantees pip_size, while quote, epoch, bid, and ask may be optional.

- Historical ticks: https://developers.deriv.com/docs/data/ticks-history/
- Live ticks: https://developers.deriv.com/docs/data/ticks/
- Current public Options WebSocket overview: https://developers.deriv.com/docs/intro/api-overview/

Run the read-only schema probe before collecting research data:

    python scripts/audit_deriv_tick_schema.py --symbol R_100 --count 500

The symbol is an explicit argument so the audit does not silently assume the target market. The probe uses the public market-data endpoint only. It does not authenticate, inspect balances, submit orders, or grant capital authority.

## 2. Feature names and permitted interpretations

- Tick direction: +1 when the observed quote rises, -1 when it falls, and 0 when unchanged.
- Signed tick-count proxy: sum of tick directions. This is not volume delta because a historical tick observation is not documented as an individual aggressor-classified trade.
- Rolling signed tick-count proxy: trailing 60-second and 900-second sums, based on timestamps and inclusive window boundaries.
- Tick frequency: count of observed price updates in a time window. This is not traded size and must not be called institutional volume.
- Spread: ask minus bid only when both values are supplied and valid. Missing bid/ask means spread is unknown, not zero.
- HVN/LVN context: optional price-bin visitation-frequency proxy. Results must be named HVN_TICK_FREQUENCY_PROXY or LVN_TICK_FREQUENCY_PROXY; they are not volume-profile nodes.
- Price/delta divergence: causal comparison of a new price extreme with proxy signed-tick-count delta at the previous extreme. It is a heuristic feature, not proof of passive absorption.
- Genuine order-flow imbalance (OFI), aggressor delta, trade-size distribution, and stop-run volume confirmation remain unavailable unless a verified source supplies the required order-book sizes or trade prints. Bid/ask prices alone are insufficient for depth OFI.

Flat ticks contribute zero to signed tick count. Carrying prior direction across an unchanged price can fabricate directional activity and is not used here.

## 3. Schema audit and data-quality requirements

For every asset and collection period, retain the report alongside raw-data provenance. The report records schema, counts, time range and price range by default. Verify:

1. Price/time arrays exist, have equal lengths, contain finite values, and timestamps are nondecreasing.
2. Symbol, timestamp units, precision, duplicates, gaps, history limits, request latency and reconnection behaviour are captured.
3. Bid/ask features are enabled only if both fields are observed and semantically verified.
4. No code path invents volume from price movements. If true volume is absent, use proxy feature names and mark volume-profile, trade-size and OFI features unavailable.
5. Historical data and live data are not presumed to have identical field coverage.

Public ticks are only the start of a data audit. They are not authenticated broker-account evidence and cannot be used to assert execution capability.

## 4. Event-conditioned triple-barrier labels

An MSNR event is timestamped at the close of the bar where it becomes knowable. Entry starts at the next bar's open. The target distance supplied for that event must be computed only from data available by the signal close. The upper/lower distances use the configured profit-taking and stop-loss multipliers.

- Profit target first: label +1.
- Stop loss first: label -1.
- Vertical barrier: label is the sign of the event-side-adjusted return (+1, -1, or 0).
- Stop and target both touched in the same OHLC bar: stop is assumed first, conservatively.
- A gap through the stop uses the worse opening price.
- If no barrier is touched and the full vertical horizon is missing at the end of the dataset, the event is omitted rather than assigned a shorter horizon.

The implementation accepts only event records selected by the caller; it does not manufacture MSNR signals. It reports directional underlying-price return for research labeling, not Deriv contract P&L. Contract-purchase strategy labels and economics must be checked against exact contract payout mechanics before inference.

## 5. Validation protocol

1. Run unit tests under normal Python and optimized Python (python -O) so correctness does not depend on assert statements in guards.
2. Add prefix-stability checks for every feature generator: future records must not alter a feature computed for a past timestamp.
3. Preserve time-ordered train/validation/test splits, walk-forward evaluation, event-level separation/embargo where labels overlap, and a final holdout never used for parameter selection.
4. Report label balance, event count, class-wise precision/recall, calibration, Brier score, net expectancy, uncertainty, drawdown, cost stress and multiple-testing exposure. A win rate or profitable in-sample result does not qualify a strategy.
5. For tick-level or event-driven execution evaluation, model latency, bid/ask spread, slippage, rejected orders, API limits and broker settlement. OHLC alone cannot determine intrabar barrier ordering; use conservative assumptions or verified tick replay.
6. Treat each asset, regime, horizon and strategy as a separate research cohort until evidence supports pooling.

## 6. Layer 6 integration and hard vetoes

This module has no runtime registration, credentials, execution transport, risk authority or live-order permission. Research agents may propose a signal and evidence only. Layer 6 and the existing release authority remain authoritative.

Before any separately approved runtime integration:
- Market-data latency greater than the configured 200 ms ceiling must veto the signal. Measure client-side request/receive latency with a monotonic clock; do not equate timestamp age or wall-clock skew with network latency.
- Rolling realized slippage beyond the reviewed threshold over the configured number of fills must pause the agent and require risk-authority clearance before resumption.
- Missing or stale data, missing spread inputs where required, proxy-feature drift, an uncalibrated probability, incomplete cost assumptions, failed OOS qualification, or unknown contract economics must fail closed.
- These are requirements for Layer 6 to enforce and evidence; passing research tests cannot satisfy a release gate.

No slippage threshold, asset mapping, or probability calibration should be inferred from this document. The example latency ceiling is a veto threshold, not proof that a 199 ms strategy is profitable.
