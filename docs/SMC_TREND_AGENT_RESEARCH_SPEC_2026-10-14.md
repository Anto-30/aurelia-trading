# AURELIA SMC Trend Agent — Research Specification (2026-10-14)

## Status

**Research-only / unqualified / no execution authority.** This change adds a deterministic candidate detector and unit tests. It does not change the canonical execution adapter, risk engine, live lock, strategy promotion policy, deployment, or production configuration.

- Strategy ID: **SMC_TREND_15M**
- Data input: completed 15-minute OHLC bars plus completed 1-hour OHLC bars
- Implementation: research/labs/smc_trend_agent.py
- Tests: research/labs/tests/test_smc_trend_agent.py
- Default numerical settings are explicit hypotheses, not empirically fitted or validated parameters.

## Precise definitions

**Bars and timestamps.** Each input timestamp is the close time of a completed bar and must be timezone-aware. Bars must be strictly increasing, prices must be finite and positive, and OHLC geometry must be consistent. The caller must supply only completed bars. Higher-timeframe rows whose close timestamp is later than the latest 15-minute close are excluded.

**ATR.** True range is TR(t) = max(H(t)-L(t), abs(H(t)-C(t-1)), abs(L(t)-C(t-1))). The first bar uses H(0)-L(0). Wilder ATR is seeded with the simple mean of the first n true ranges and then updated as ATR(t)=((n-1)*ATR(t-1)+TR(t))/n. No signal is returned before the warm-up completes.

**Confirmed swing high/low.** A swing at index i is confirmed only after the configured number of right-hand bars has closed. A swing high must have a strictly greater high than all configured bars to its left and right; a swing low must have a strictly lower low than all configured bars to its left and right. This intentionally avoids treating an unconfirmed, still-forming pivot as known.

**Structure bias.** With the two latest confirmed swing highs and lows, higher-high plus higher-low means BULLISH; lower-high plus lower-low means BEARISH; mixed or insufficient structure means NEUTRAL.

**BOS / CHoCH.** A bullish break requires the latest completed candle to close above the most recent confirmed swing high and have a positive body at least displacement_atr_multiple * ATR. A bearish break is symmetrical below the most recent confirmed swing low with a negative candle body of at least that size. The break is labelled CHoCH only when it opposes the pre-break structure bias; otherwise it is labelled BOS. Neutral pre-break structure is labelled BOS for this version and should be preserved as a separate audit field (prior_structure_bias=NEUTRAL).

**Fair Value Gap.** On the current completed bar t, bullish FVG exists when H(t-2) < L(t), with zone [H(t-2), L(t)]; bearish FVG exists when L(t-2) > H(t), with zone [H(t), L(t-2)]. Gap width must be strictly greater than min_fvg_atr_multiple * ATR(t). Default minimum is 0.5 ATR as a research hypothesis, not a calibrated market fact.

**Order block.** For a bullish setup, the order block is the most recent bearish candle among the preceding order_block_lookback_bars; for a bearish setup, it is the most recent bullish candle. The entire candle range is retained as the zone. This is a deterministic proxy, not proof of institutional order placement or resting liquidity.

**Entry, stop and target references.** By default, entry is the 50% midpoint of the qualifying FVG; configuration also permits the 50% midpoint of the order-block candle. A long candidate is rejected unless entry is below the signal close and its stop is below entry. A short candidate is rejected unless entry is above the signal close and stop is above entry. The stop reference is placed beyond the order-block boundary by stop_buffer_ticks * verified_tick_size. The default target is target_multiple_r times the entry-to-stop risk distance (2R by default). Candidate is rejected if the target was already crossed by the signal close. These are **research price references**, not a claim that the selected Deriv contract supports a native stop, limit, OCO, or price-based close.

**One-hour confirmation.** With the default policy, a setup is eligible for research only when the last fully closed 1-hour structure bias is directional and agrees with the 15-minute setup. Neutral or missing higher-timeframe structure fails closed.

**Pending-setup status.** A later completed bar closing beyond the full order-block boundary invalidates the setup. That check takes precedence over a simultaneous entry-level touch. Intersecting the entry reference is recorded only as ENTRY_LEVEL_TOUCHED; OHLC data cannot establish queue priority or a true fill. A setup expires after max_pending_bars unless invalidated or touched first.

## Current guardrails and important Deriv distinction

1. Research code emits candidates only. The fields capital_authority=false and order_submission_permitted=false are hard-coded in the output.
2. The canonical repository uses the modern Deriv Options API path. Deriv documents market-data streams/history separately from proposal/buy/sell contract operations. A price-based SMC stop/target must **not** be assumed to map directly onto a fixed-payout or other Options contract. Before any instrument can qualify, its exact account type, symbol/contract type, payoff, minimum stake, increments, exit support and settlement rules must be verified using the existing instrument-specification and cost-profile gates.
3. The public tick API provides timestamped quotes. A count of received ticks is an **observed tick-arrival rate**, not exchange volume or centralized order flow. It must not be named true traded volume or DOM. This initial 15-minute phase does not require volume confirmation.
4. The Deriv ticks-history candle schema documents supported granularities including 60 seconds, 300 seconds, 900 seconds and 3600 seconds. A 1-minute bar alone cannot validate a sub-3-second trigger; the future scalping phase will need timestamped tick streams and latency/slippage observations.
5. Cost inputs of UNKNOWN must remain UNKNOWN and block qualification. Never set spread, fees or slippage to zero merely because they are unavailable.
6. Do not change config/LIVE_LOCK.yaml, capital sizing, execution adapters, release gates, or deployment in this research PR.

Official API references:
- [API Overview](https://developers.deriv.com/docs/intro/api-overview/)
- [Ticks Stream](https://developers.deriv.com/docs/data/ticks/)
- [Ticks History](https://developers.deriv.com/docs/data/ticks-history/)
- [Price Proposal](https://developers.deriv.com/docs/trading/proposal/)
- [Buy Contract](https://developers.deriv.com/docs/trading/buy/)
- [API Limits](https://developers.deriv.com/docs/limits/)

## Validation protocol before any promotion

### Stage 0 — correctness and data lineage
- Run repository assurance and unit tests; preserve the exact branch SHA and test outputs.
- Check missing/duplicate/out-of-order bars, timestamp semantics, symbol identity, candle-close completeness, tick size and precision.
- Verify swing confirmation and FVG/OB coordinates against independently labelled examples. The detector test fixture is synthetic software test data, not market performance evidence.
- Ensure no future bar is used to calculate a feature, pivot, signal, higher-timeframe bias or fill.

### Stage 1 — baseline, no ML
- Use a frozen data snapshot and versioned instrument specification.
- Run a deterministic event-driven backtest; enter only after the signal bar closes, model the earliest permitted retracement entry, and record stop/target ambiguity conservatively. Do not assume price touched equals filled.
- Account for spread, slippage, commissions/fees, payout/payoff model, rejected orders, latency and the relevant instrument-specific costs. Do not mix underlying-price returns with contract-P&L returns.
- Report trade count, expectancy per trade in R and currency, gross/net profit factor, maximum drawdown, Sharpe, Sortino, Calmar, tail loss, average win/loss in R, turnover, holding time, adverse/favourable excursion, fill rate and sensitivity to costs. Report win rate only as a secondary diagnostic.
- Compare the full SMC specification to simple BOS-only and FVG-only ablations. If SMC confluence adds no stable incremental value after costs, remove complexity rather than tune until it passes.

### Stage 2 — rolling walk-forward and prospective OOS
- Initial protocol hypothesis: 3 calendar months in-sample, then 1 calendar month OOS; move forward one month and repeat. Use chronological windows only, never random K-fold.
- Purge the boundary by at least the maximum label/holding period. Fit thresholds, any scaling, calibration, regime cutoffs and meta-model parameters only on the in-sample segment. No retuning after an OOS segment is sealed.
- Preserve separate results per strategy × symbol × regime. Include a sealed prospective OOS stream and follow the current AURELIA validator's sample requirements; an underpowered cell is INSUFFICIENT_SAMPLE, not a pass.
- Record the complete tested-configuration count, multiple-testing adjustment, code/data/config hashes, cost profile, source timestamps and exclusions.
- Stress test higher spread and slippage, 200 ms and worse latency, missed ticks, data gaps, delayed fills, realistic price rounding, gaps through stops and parameter perturbations.

### Stage 3 — promotion evidence (not granted by this PR)
Promotion requires positive out-of-sample net expectancy after verified costs, stable walk-forward metrics, acceptable drawdown/tail risk, calibration and drift controls where probabilities are used, instrument qualification, and independent review. Production qualification additionally requires the existing authenticated Deriv session verification, verify-only broker lifecycle and reconciliation evidence, persistent-runtime health, required soak and deterministic release gate. Passing software tests or a strong backtest cannot authorize live capital.

## Failure modes to test

- False structural breaks during noisy/high-volatility bars when the ATR-normalized threshold is too low.
- Very few or no trades when displacement and FVG thresholds are too strict.
- FVG midpoint never retraces, or retraces only after the OB invalidation level is breached.
- High volatility spikes distort ATR and make otherwise plausible setups untradeable after stops/costs.
- 1-hour structure is neutral or lags a true reversal.
- A gap measured from OHLC has no tradable edge after bid/ask, slippage, latency, contract payout and fill uncertainty.
- Definition choices (strict swing pivots, OB lookback, entry zone and 2R target) materially change the result; if minor parameter perturbations reverse the sign of expectancy, classify the strategy as unstable.

## Next phases (not part of this PR)

**Phase 2 — 1-minute scalping:** implement only after its data contract is approved. Require tick-stream timestamps for velocity, explicitly call tick count an arrival-rate proxy, use verified spread and latency distributions, and perform a 200 ms plus empirical p95/p99 slippage stress. Abort when required cost inputs are unknown. A 1-minute candle feed cannot prove a sub-3-second condition.

**Phase 3 — 5-minute mean reversion:** define ADX(14), Bollinger Band Width contraction, RSI(14), and reversal candle logic deterministically. Validate only in the range regimes where the filter is satisfied. Do not label the model as an edge until cost-adjusted prospective OOS is positive.

**Ensemble/meta-router:** do not combine agents or boost position size merely because signals agree. First qualify each standalone strategy. Later compare a no-trade-on-conflict baseline with alternatives using sealed OOS data; use shrinkage and minimum-sample gates on rolling Sharpe, enforce one shared portfolio-level risk budget and correlated-exposure limits, and let only the existing deterministic capital plane authorize sizing. A rolling 30-day Sharpe alone is noisy and must not be treated as a sufficient allocation signal.
