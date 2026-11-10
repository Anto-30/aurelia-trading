# ATOS v2.0 SMC Research Backtest

## Scope and authority

This module is research-only. It does not import AURELIA runtime order adapters, read broker credentials, submit proposals, buy contracts, execute trades, modify config/LIVE_LOCK.yaml, or grant capital authority.

Hard-coded safety assertions:
- RESEARCH_ONLY = true
- CAPITAL_AUTHORITY = false
- ORDER_SUBMISSION_PERMITTED = false
- LIVE_EXECUTION = BLOCKED
- FINAL_EXECUTION_AUTHORIZATION = false

Do not move these strategy detectors into production or connect them to an order router. Qualification requires a separately approved research evidence package and the existing AURELIA deterministic promotion/release chain.

## Data and timestamps

The primary dataset is Deriv public 1-minute OHLC candles for the exact requested symbol, using the current no-auth WebSocket endpoint `wss://api.derivws.com/trading/v1/options/ws/public`. The downloader:
- resolves the current symbol through public active_symbols;
- retrieves ticks_history candles with granularity=60, explicit count, style=candles, and subscribe=0;
- pages backward, deduplicates timestamps, validates OHLC, and does not forward-fill missing bars;
- writes the raw normalized OHLC CSV and a JSON report with the coverage assessment.

All candle indices represent the candle open time in UTC. The strategy engine computes close availability as open time + timeframe. 15-minute bars are formed only from 15 observed 1-minute bars and only become available at their 15-minute close. Fractals are confirmed only after the configured right-hand bars close.

Yahoo Finance is supported for Yahoo-listed instruments. It is not a source for Deriv synthetic indices. Its 1-minute intraday history is limited to 60 days; the CLI rejects 90-day 1-minute yfinance requests instead of using a silently truncated sample. A 90-day Deriv synthetic-index baseline must use Deriv's public historical endpoint.

## NY time window

Default TimeWindow is America/New_York, from 00:00 through an inclusive 08:50 cutoff. The start time is configurable because the source prompt supplied a cutoff but did not define the beginning of the active window.

The 1-minute candle stamped 08:49:00 New York closes at 08:50:00 and may produce a signal. Pending limits are eligible only at later bar opens inside the window. At exactly 08:50, an already marketable limit may fill at the open; a non-marketable resting limit is cancelled and cannot fill from a later intrabar low/high. Existing positions continue to be managed after the cutoff. This defines signal evaluation, not a claim about exchange session hours.

## Strategy 1 — Supply/Demand + directional structure break

- 1-minute swing structure is based on two-left/two-right fractal pivots by default; each pivot is usable only after the right-hand bars close.
- 15-minute directional bias uses the same confirmed HH/HL or LH/LL structure and is mapped to 1-minute bars only after the 15-minute candle closes.
- A signal requires aligned 1-minute and 15-minute directional structure and a body close crossing the most recent confirmed swing high (long) or swing low (short).
- The origin is the nearest prior opposing-colour 1-minute candle in a configurable lookback. Its full high/low is the zone; its open is the proximal entry.
- The order is ignored if the proximal line was already mitigated before the CHoCH proxy.
- Stop is one 1-minute ATR(14), known before the signal candle, beyond the zone distal wick.
- Target is the nearest already-confirmed opposing swing beyond the signal close. The trade must have at least 3R planned reward/risk.

The user's CHoCH rule is operationalized as a directional close through the last confirmed swing. SMC definitions vary; this is an explicit close-confirmed structure-break proxy, not a universal definition of CHoCH.

## Strategy 2 — Prior-session sweep + displacement/BOS + FVG CE

Default prior liquidity windows (New York local time) are explicit assumptions:
- Asia: 19:00 on the prior New York date through 00:00 on the current date.
- London: 02:00 through 05:00 on the prior NY date.

Change these in Strategy2Config if the videos use different session definitions. The engine builds prior-session highs/lows, equal highs/lows using a two-pip-increment tolerance, and unmitigated 3-candle FVG pools. For a signal on date D it uses the Asia session ending at 00:00 on D and the completed London session from 02:00-05:00 on D-1; it never uses the still-forming D London range. It rechecks that a prior-session FVG has not been mitigated between its formation and the candidate sweep.

A sweep requires the wick to pierce the liquidity boundary by the configured minimum and the candle body to close back inside. A close through the swept boundary is not a valid sweep (inversion); it is rejected. Following a sweep, a later candle must have body size strictly greater than 1.5 times ATR(14) calculated only from prior candles, close through a confirmed swing BOS level, be aligned with 15-minute bias, and create a new three-candle FVG. If a displacement candle occurs without all BOS/FVG/MTF conditions, that sweep is discarded. The CE entry is the new FVG midpoint; stop is beyond the original sweep wick plus a tick buffer; target is the nearest prior-session opposing high/low pool beyond the displacement close.

The default time windows are assumptions because the user supplied no exact Asian/London session definitions from the videos.

## Event-driven fill model

A custom sequential pandas/NumPy OHLC simulator is used rather than vectorbt/backtrader signal arrays. This model has stateful pending limits, setup invalidation, one-position exposure, a mark-to-market daily breaker and intrabar stop/target collisions. A signal-array engine without custom order state would not encode these mechanics faithfully.

Rules:
- Signals are known only after the signal candle close. A limit cannot fill on its signal candle.
- A later candle open that is already through the limit is filled at the open; otherwise a touch fills at the limit.
- A same-candle stop and target collision is resolved stop-first.
- For a candle that first fills an intrabar limit and also touches the target, the target-only outcome is not credited because OHLC cannot determine whether target happened before entry. A stop can still be booked on that fill candle. If neither stop nor later candle target occurs, the trade is marked at the final close at end of data.
- Gap-through stops are filled at the opening price when worse than the stop.
- One position at a time; unfilled limits expire or cancel after the NY cutoff.
- 1% fixed-fractional modeled risk per trade; daily mark-to-market drawdown >=3% halts new entries for that New York date and cancels pending orders. Positions remain subject to stop/target management.

These are conservative simulation conventions, not a guarantee of executable fills on Deriv.

## Risk sizing and economics

The quantity is normalized from:
risk_cash = current_equity * risk_fraction
risk_per_unit = abs(entry - stop) * point_value + estimated_round_trip_cost_per_unit
quantity = risk_cash / risk_per_unit

The defaults point_value=1.0, zero spread, zero slippage and zero commission are unverified model assumptions. On Deriv, active_symbols.pip_size is used as the provider-published price increment (for example, the current New API example shows R_100 pip_size=0.01). A sourced --tick-size can override it. This value does not provide a contract cash multiplier or payout function. Do not describe normalized quantity/cash output as actual stake or broker P&L until contract multiplier, minimum stake, stake increment, payout/payoff, spread/slippage/commission and exact pricing basis are separately sourced and verified.

## Metrics

The JSON output includes:
- Expectancy: average net R per completed trade.
- Profit Factor: gross gains divided by absolute gross losses; if there are no losses, PF is null (undefined from sample), not a fabricated finite number.
- Maximum drawdown: percentage from peak marked equity.
- Sharpe: annualized from daily marked-equity returns, using sqrt(365) because synthetic indices trade continuously; the convention is disclosed.
- R-multiple distribution: count, p05, p25, median, p75, p95, mean and standard deviation.
- Trade ledger, rejected/cancelled order counts, equity curve, source metadata, data gaps, and assumption verification flags.

No raw win-rate summary is used as a selection metric. No strategy is automatically promoted because it has higher in-sample PF. A model must survive prospective/out-of-sample evaluation, regime splits, parameter stability and verified transaction costs before any strategy eligibility decision.

## Look-ahead and selection-bias controls

1. Fractals are not visible until the right-hand confirmation candles close.
2. ATR used to qualify a candle is shifted and uses only prior candles.
3. MTF bias is joined by available_at = 15m open + 15m, never by the 15m opening timestamp.
4. The signal's order cannot fill until the next candle.
5. Prior-session FVGs are filtered for mitigation using only bars before the candidate sweep.
6. Stops/targets use deterministic conservative collision rules.
7. Gaps, duplicates, invalid OHLC and naive timestamps are errors or explicit coverage deficits; no forward-fill.
8. The 90-day baseline is exploratory/in-sample unless followed by a genuinely untouched time period or prospective run. Optimizing thresholds on the same 90 days and then reporting its PF is selection bias.

Remaining risks include OHLC's inability to expose intrabar price path, data-provider revisions, quote gaps, latency, fill queue/limit non-fill, instrument specification changes, and session-window choice. Preserve the raw CSV and JSON result with run SHA, and use a separate holdout or prospective data collection before making an edge claim.

## Run

Install research-only dependencies separately from the runtime:
pip install -r requirements.txt -r requirements-research.txt

Provisional 90-day V100 run using the provider-published Deriv pip_size:
python -m research.labs.run_smc_baseline --provider deriv --symbol R_100 --days 90

This creates a JSON report and normalized OHLC CSV under reports/research/atos_smc_v2/. For a stronger test, supply sourced minimum tick size, verified contract point value, and sourced round-trip spread/slippage/commission inputs. The manual GitHub Actions workflow only downloads public candles and saves artifacts; it never receives user/broker secrets or submits trades.
