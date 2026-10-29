# Phase 6 / Phase 6+Layer 9 Time-Filter Research Specification

Status: \`RESEARCH_ONLY_UNQUALIFIED\`. This specification is a reproducible hypothesis, not an edge claim.

## Model definitions

Both models require timezone-aware, minute-aligned OHLC data indexed by each bar's **opening timestamp** and normalized to \`America/New_York\`. The signal is computed only after the bar timestamped 08:50 has closed. Entry uses the next minute bar's open, expected at 08:51. Exact 08:50 matching is required; no nearest-bar fallback is implemented because an 08:50 New York wall-clock time exists on both sides of a daylight-saving transition. Missing data causes the candidate to be skipped.

### Phase 6 only

- Long: target bar at 08:50 NY, \`close > open\`, and \`close > EMA(20)\`.
- Short: target bar at 08:50 NY, \`close < open\`, and \`close < EMA(20)\`.
- Stop distance: 1.0 × true range of the signal bar. True range includes gaps from the previous close.

### Phase 6 + Layer 9

Apply the same candle and EMA(20) rules, plus:

- \`volume > 1.5 × mean(volume of the prior 20 bars)\`. The signal bar's volume is intentionally excluded from the reference mean.
- Long only if \`close > EMA(200)\`; short only if \`close < EMA(200)\`.
- Wilder ATR(14) must be greater than its preceding value.
- Stop distance: 1.5 × Wilder ATR(14), calculated at the signal bar close.

## Execution simulation

- Signal timestamp: 08:50 bar close; because data timestamps represent bar opens, its information is only available at 08:51.
- Entry: next bar open at 08:51; apply adverse one-way slippage.
- Time exit: close of the bar timestamped 09:05, whose wall-clock close is 09:06. This implements 15 minutes from the 08:51 entry open. If the input vendor labels bars differently, convert timestamps before running; do not assume bar timestamp semantics.
- Stop checks use OHLC high/low and stop-first precedence. If the opening price has gapped beyond the stop, simulated stop fill is the bar open; otherwise the stop price. The triggering bar is recorded but exact stop-execution time and holding duration remain unknown from OHLC alone. This is an OHLC approximation, not tick-level execution evidence.
- If entry minute, scheduled exit bar, or any one-minute bar during the hold is missing, skip the trade and record a reason. No trade is assumed over a gap.
- Commission and one-way slippage per share are mandatory CLI inputs. Explicit zero is allowed only for a sensitivity scenario and must not be described as actual market cost.
- One candidate per New York calendar date. Short-sale borrow costs, market impact, and venue-specific fees are not modeled; net statistics remain incomplete for an execution-grade study until relevant costs are supplied.

## Data and indicator integrity

All indicator calculations use only current/past rows. EMA warm-up bars and ATR warm-up bars produce no signal. The source DataFrame is copied and not mutated. Datetime indexes must be timezone-aware, sorted, unique, and minute-aligned; OHLC values must be finite, positive, and internally consistent. Volume is mandatory for Phase 6+Layer 9.

## Reproduction

Install research dependencies separately from the live runtime:

\`\`\`bash
pip install -r requirements-research.txt
\`\`\`

Run both models with explicit costs:

\`\`\`bash
python -m research.labs.phase6_time_filter \\
  --data /path/to/NVDA.parquet \\
  --timestamp-column timestamp \\
  --source-timezone UTC \\
  --commission-per-share-per-side 0.005 \\
  --slippage-per-share-per-side 0.01 \\
  --oos-start 2026-07-01 \\
  --outdir artifacts/phase6_nvda
\`\`\`

The sample cost numbers above are illustrative inputs, not verified execution costs. Replace them with the actual brokerage/venue cost model. For US-listed equities, 08:50 New York is premarket; use an extended-hours dataset and costs that reflect the wider spread and lower liquidity, or the test is not representative of a fillable setup. If timestamps already contain a timezone, \`--source-timezone\` is not used. Naive local timestamps around a DST fold must not be silently localized; ambiguous/nonexistent values abort.

Outputs include a SHA-256 hash of the Parquet input, source revision when available, the full/partitioned metrics, trade-ledger CSVs, and skipped-signal reasons. Metrics are simulated research evidence, not broker truth.

## Interpretation / promotion policy

Do not claim predictive edge from one instrument/date range, gross P&L, zero-cost runs, or in-sample statistics. Compare Phase 6 only against Phase 6+Layer 9 on the same bars and cost model; keep parameters frozen before the OOS start date. Report closed-trade count, expectancy per share and R, net profit factor, win rate, maximum drawdown in cumulative R, fees, slippage, skipped setups, and uncertainty. Repeat across multiple chronological windows and symbols; adjust statistical confidence for multiple trials. A favorable test does not qualify execution or authorize capital. The AURELIA live lock and deterministic capital plane remain unchanged.
