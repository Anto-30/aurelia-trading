# Layer 9 deterministic structure and 3-6-9 research specification

**Status:** research implementation; not production-qualified.
**Module:** research/labs/market_structure_369.py
**Tests:** research/labs/tests/test_market_structure_369.py
**Authority:** RESEARCH_ONLY=true, CAPITAL_AUTHORITY=false, LIVE_EXECUTION=false, ORDER_SUBMISSION_PERMITTED=false.

## Scope

This package codifies M15 protected-level sweep → M1 market-structure shift → first aligned FVG midpoint-retest, with an optional 3-6-9 projected-level filter. It is separate from AURELIA's authenticated adapter and capital plane. It does not modify LIVE_LOCK, grant capital authority, or submit orders.

## Protected swing and BOS/MSS

A pivot uses configurable left/right confirmation bars (default 2/2); it is not observable until all right-side bars close. Equal-high/equal-low clusters are rejected. Candidate pivots and displacement breaks require uninterrupted, non-synthetic bars.

Bullish BOS requires the prior close to be at or below the latest unconsumed confirmed swing high, and the current candle to close strictly above it with a bullish body. Bearish logic is symmetric. Displacement is absolute candle body divided by the mean true range of the prior 10 closed candles, excluding the break candle; the ratio must be strictly greater than 1.5. A weak close-through consumes the level. A later candle cannot retroactively upgrade it.

The protected point is the latest confirmed opposing pivot formed after the broken pivot and not invalidated before the displacement break. This is a deterministic approximation, not a universal definition of ICT terminology.

## Fair Value Gaps

For the third candle at index i:
- Bullish: Candle 1 high < Candle 3 low; zone is [Candle 1 high, Candle 3 low].
- Bearish: Candle 1 low > Candle 3 high; zone is [Candle 3 high, Candle 1 low].

The midpoint is the arithmetic mean of zone boundaries. A later candle mitigates a bullish gap when its low is at or below the midpoint, and a bearish gap when its high is at or above the midpoint. The creating candle cannot mitigate its own gap. A data gap or synthetic candle makes an open gap stale. Use active_fvgs_at() for causal as-of queries; do not use full-history mitigation state to make past decisions.

## Session and timeframe alignment

New York AM is 07:20–10:45 America/New_York, DST-aware, inclusive at both boundaries. It is the only enabled default. London is configurable through an explicit SessionWindow; its exact phase is not guessed.

M15 bars use 900-second spacing and M1 bars use 60-second spacing. The M1 confirmation window begins at the exact M15 candle-close time and is [start, start + N). If the first M1 candle is missing, the setup is rejected rather than shifting the timer. A close through the sweep extreme invalidates the setup. Gaps or synthetic M1 bars abort confirmation.

## 3-6-9 mapping

The digital root of the positive integer int(reference price / price quantum) maps 1/4/7 → 12, 2/5/8 → 15, and 3/6/9 → 18. Multiply the base step by instrument step_unit. Project integer multiples above and below the exact protected swing and quantize them to the instrument tick. Alignment is checked against the M15 sweep extreme, not the entry price.

This mapping is a falsifiable hypothesis, not an established market law. The original brief did not define a complete XAUUSD/NQ/Deriv scaling convention. price_quantum, step_unit, tick size and tolerance require source-backed instrument metadata. The metadata verified flag and source digest are operator attestations, not cryptographic verification. Negative, zero, non-finite and sub-quantum inputs fail closed.

## Deriv historical data pipeline

The read-only research adapter uses the public modern market-data WebSocket:
wss://api.derivws.com/trading/v1/options/ws/public

It requests ticks_history candle data for granularity 60 (M1) or 900 (M15), with bounded start/end epochs and up to 1,000 candles per page. It does not send subscribe, count, login, OTP, proposal, buy or sell requests. It is a separate research utility; runtime/adapters/deriv_adapter.py is not changed.

Responses are checked for echoed symbol/style/granularity, candle message type, integer and aligned epochs, duplicates, chronological order, interval consistency and request bounds. Each response/request pair is hashed. Missing bars may be dropped or forward-filled for diagnostics; forward-filled bars are marked synthetic and excluded from structure/FVG signals and the experiment.

A successful API call or mock test is not source verification. An independently reviewed acquisition receipt and attestation must be provided before manifests can be marked source_verified. Both M1 and M15 datasets must match exact requested window endpoints, be non-synthetic and contiguous, have matching symbols and at least 183 days of overlap. No live Deriv data was fetched in this code change.

## Control-versus-Test harness

Both groups start from the same candidate set and identical structure conditions:
- Control: every eligible M15 sweep → M1 MSS → first aligned FVG midpoint retest.
- Test 369: only setups whose M15 sweep extreme lies within tick tolerance of a projected level from the exact protected swing.

Entry is the FVG midpoint. Stop is beyond the FVG invalidation edge by stop_buffer_ticks × instrument tick (default one tick). Target is fixed 2R. Opposing-liquidity TP is not implemented in this version.

Outputs include trade count, win rate, gross expectancy in R, profit factor and realized-R maximum drawdown. Net metrics are only populated with a verified cost-per-trade model; missing costs remain null/UNDETERMINED, never zero. A gross-only result cannot qualify the 369 layer for promotion.

The default decision gate requires at least 201 Test trades, at least +0.10R expectancy improvement and a paired moving-block bootstrap lower confidence bound above zero, OR a positive lower confidence bound for drawdown improvement. The bootstrap resamples paired five-calendar-day blocks; zero-trade calendar days are retained. A passing result only retains the numerical layer for prospective OOS validation. It does not establish live tradability or execution authority.

## Reproducibility and qualification

The experiment records the hypothesis ID, code commit, configuration hash, M1/M15 dataset hashes, acquisition evidence, data window, frozen configuration, deterministic random seed, trial count, statistical gate and limitations. The run requires a 40- or 64-character code commit SHA and source-attested datasets.

Install and test:
python -m pip install -e '.[research]'
python -m unittest research.labs.tests.test_market_structure_369 -v

## Known limitations

1. No source-verified Deriv candles have been downloaded, and no six-month backtest has run.
2. No expectancy, win rate, PF, drawdown, bootstrap or numerical-layer edge claim is available.
3. R_100 spread, slippage, latency and fees have not been calibrated; net expectancy is unknown.
4. XAUUSD/NQ scaling fixtures are arithmetic examples, not validated contract specifications. Deriv 369 quantum/step configuration remains unresolved.
5. OHLC midpoint fills are approximate; tick replay is needed for event ordering and fill quality.
6. Portfolio exposure, concurrent trades, rejected orders, partial fills and account-level drawdown are not modeled.
7. Opposing-liquidity take profit is not implemented.
8. London times remain unset pending the exact intended phase.
9. Claude Code, DeepSeek code completion and Hermes runtime execution are not asserted without evidence from those runtimes.

The canonical AURELIA lock remains unchanged: LIVE_EXECUTION=BLOCKED, capital_plane_mode=VERIFY_ONLY, FINAL_EXECUTION_AUTHORIZATION=false, research_capital_authority=false.
