# T4F × 369 Research Readiness Audit v0.1.0

**Status:** Research-only engineering draft. Not a frozen strategy. Not approved for automated execution.

## Work package

This branch contains pure numerical primitives, observable candle-interaction classification, delayed pivot-candidate labeling, a read-only public Deriv market-data client, cost-aware descriptive trade metrics, tests, and a bounded-object TradingView level projector.

The module deliberately does not create a full signal or trade simulator. The supplied T4F specification does not yet define the protected-swing/BOS rules, decisive-break threshold, FVG pattern and invalidation, CISD displacement, STDV calculation, exact opening-reference timezone, entry fill mechanics, or the stop/target policy tightly enough for reproducible strategy outcomes.

## Preserved numerical rules

- Digital root is chosen from the positive integer part of the protected swing reference.
- The base step mapping remains 1/4/7 → 12, 2/5/8 → 15, 3/6/9 → 18.
- The full reference price, including decimals, is retained for level projection.
- XAUUSD multiplier is 1; NQ multiplier is 10.
- ES multiplier is 1 only as the supplied provisional mapping; its calibration status is explicitly UNVERIFIED.
- Four levels are the minimum. The numerical projector does not create a buy/sell signal.

## T4F rules not silently approximated

### Protected swing and structure
The text says that a protected swing is the swing that initiates a move that breaks an opposing structural level. It does not define the swing pivot algorithm, exact BOS close/wick requirement, what makes a level meaningful, how many bars can elapse between the swing and break, or how overlapping/multiple candidate swings are resolved. A mechanical pivot is therefore only a pivot candidate, never a Protected Swing.

### M15 interaction
The text distinguishes body close through a level from a wick rejection. It does not quantify "decisive". The code records a body cross but marks decisiveness undefined. A wick rejection is not an entry signal.

### M1 confirmation / FVG / CISD
The text requires MSS/BOS, the first aligned FVG, a 50% retrace, and CISD. It does not define the pivot/structure algorithm, 3-candle FVG boundaries, minimum gap, first-FVG selection if multiple gaps form, invalidation price/buffer, or displacement threshold. Those must remain human-reviewed or unresolved; this branch does not fabricate them.

### STDV exits
The four extension values (38.2%, 61.8%, 100%, 161.8%) are specified, but the anchor, sample series, standard-deviation estimator/window, and whether levels are projected from entry or a session range are not. No target prices or R:R are generated.

### Session clocks
The 07:20–10:45 America/New_York interval is 205 minutes. Exact fractional boundaries:
- 0.315: 64.575 minutes after 07:20 = 08:24:34.5
- 0.630: 129.15 minutes after 07:20 = 09:29:09
- 0.810: 166.05 minutes after 07:20 = 10:06:03

The displayed values 08:30 and 09:30 are approximations, not exact boundaries. A bar-matching/rounding rule is unresolved. The London phase windows' timezone is not expressly named in the supplied text. The 00:00 and 02:22 opening references also need an explicit timezone and session/date rollover rule.

### Correlated-market SMT
NQ and ES need synchronized time series and a defined common session. The exact comparison swing window, matching tolerance, and treatment of unequal feed timestamps are not defined.

## Code behavior and limits

- `t4f_369_engine.py`: Decimal-safe digital-root mapping/projection, M15 candle interaction labels, and pivot candidates with an explicit confirmation index. The latter are not Protected Swings.
- `deriv_public_data.py`: public no-auth WebSocket market-data retrieval only. It first discovers active symbols and refuses a symbol not returned by that endpoint. It does not place orders or access accounts.
- `t4f_369_metrics.py`: validates timestamps/cost inputs and calculates net expectancy in R, net profit factor, total net PnL and drawdown with a zero starting equity peak. It does not mutate the input frame.
- `T4F_369_Level_Projector.pine`: manual reference-price level projector; creates a bounded set of chart objects once and updates them, rather than generating new objects on every bar. It does not auto-identify protected swings.
- Pivot candidate labels include the first bar at which a symmetrical pivot can be known. Any subsequent analysis must start after that confirmation bar. This prevents the original script's use of future-confirmed pivots as if they were known at the pivot bar.

## Defects in the supplied scripts

1. The supplied WebSocket client calls `run_forever()` before sending a request. It blocks waiting for messages and then attempts to send on a connection that may already be closed. The request must be sent from an on-open callback or through a synchronous request/response connection.
2. The supplied five-left/five-right pivot detector looks into future bars. Its backtest begins at pivot_index + 1, even though the pivot is not knowable until pivot_index + 5.
3. The supplied detector finds mechanical pivots, not protected swings confirmed by BOS.
4. The expression `(touched.index[0] - index) / 900` is not reliable: the DataFrame index may be a row integer or a timestamp, and neither guarantees seconds. Use explicit positional bar offsets or UTC timestamp deltas.
5. The touch test uses an arbitrary 20% step tolerance, does not distinguish a wick from a body close, and is not specified in the T4F prompt.
6. The function records a level touch, not an M1-confirmed FVG entry, stop, target, or trade PnL. Its output must not be described as backtest performance.
7. The original metrics function mutates the input DataFrame and its maximum-drawdown calculation omits the zero starting equity peak, understating drawdown when the first trade loses.
8. The original 25/25 allocation is not a clean ablation if the two groups contain different market regimes or unrelated candidate events. A more controlled comparison evaluates the same T4F-eligible candidate universe under identical entry/exit/cost rules, with the 369 eligibility filter as the only difference.

## Minimum defensible 369 value test

1. Freeze the complete T4F structural candidate rule, FVG entry/stop/exit rules, session clock rules, instrument data source, costs, and all exclusion rules before measuring outcomes.
2. Generate one event ledger containing every structural T4F setup candidate, with a stable candidate ID and exact UTC timestamps.
3. For each candidate, calculate whether it satisfies the pre-defined 369 level condition. Do not hand-select the most visually aligned swing after observing future price.
4. Evaluate hypothetical trade outcomes for every base candidate with identical fills, stop/target logic, and costs. The only variant difference is whether the 369 filter admits the candidate.
5. Keep chronological data partitions untouched until final evaluation. Report the number of candidates, retained trades, net expectancy, net PF, drawdown, net PnL, cost totals, and all exclusions.
6. Treat 25 observations per arm as a pilot, not conclusive proof. A raw 40% touch rate is not a profitability criterion. It ignores direction, entry, stop, target, transaction costs, and the economic payoff conditional on a touch.
7. Do not select the best-performing 369 root/step or session boundary after inspecting the evaluation set. If a parameter change is made, create a new version and a new untouched evaluation sample.

## Data and governance

- Historical requests use Deriv's current documented public no-auth WebSocket endpoint. Discover symbol codes from `active_symbols`; do not assume `frxXAUUSD` is available.
- Preserve raw response hash, retrieval time, symbol, timeframe, and normalized data hash.
- Validate bar order, duplicates, timezone, OHLC consistency, and expected timestamp continuity before research. Do not forward-fill or silently repair.
- Current branch contains no market dataset and no executed backtest results.
- All modules are research-only. No capital authority, proposal/buy/sell methods, live credentials, or order submission are present.
- Existing AURELIA governance remains: LIVE_EXECUTION=BLOCKED, VERIFY_ONLY, FINAL_EXECUTION_AUTHORIZATION=false.


## Additional deterministic primitives (v0.1.0 research candidates)

The implementation now also contains:
- Opening-reference comparison exactly applying the supplied rule: above either opening means LOOK_FOR_SELL; below means LOOK_FOR_BUY. Combined bias is BEARISH only when both references say sell, BULLISH only when both say buy, otherwise NEUTRAL. The 00:00 and 02:22 opening timezone/session-date policy is still unresolved, so callers must supply timestamped prices with provenance.
- Exact 07:20–10:45 America/New_York marker calculations for fractions 0.000, 0.315, 0.630, 0.810 and 1.000. The helper returns exact timezone-aware times and does not round them to M1 bars. The marker times are 07:20:00, 08:24:34.5, 09:29:09, 10:06:03 and 10:45:00 local. The bar-selection/rounding policy remains unresolved.
- NQ/ES SMT classification implementing only the supplied lower-low/no-ES-lower-low bullish condition and higher-high/no-ES-higher-high bearish condition. Input swings must be independently synchronized and preselected by the caller; exact comparison swing selection and the 09:27–09:33 window still need an explicit timestamp rule.
- A first aligned 3-candle FVG candidate detector. It uses a strict three-candle non-overlap gap formula and returns gap bounds/midpoint only when the entire three-candle sequence begins after the supplied M1 confirmation index. This is an explicitly provisional candidate rule, not owner-approved final FVG logic. It does not generate an SL buffer, entry fill, CISD, or trade authorization.

These primitives are intentionally labelled as candidate computations where the supplied rules are incomplete. They do not silently fill missing BOS, CISD displacement, STDV anchor, fill, or target definitions.


### BOS / protected-swing candidate implementation

A parameterized structure-break candidate routine has now been added. It:
- Uses only pivots whose right-side confirmation bar is strictly earlier than the proposed break bar.
- For a bearish candidate, checks whether the latest two known pivot lows form a higher low, selects the latest confirmed pivot high formed after that higher low, then checks a break of the higher-low level.
- For a bullish candidate, checks whether the latest two known pivot highs form a lower high, selects the latest confirmed pivot low formed after that lower high, then checks a break of the lower-high level.
- Exposes independent `close` and `wick` break modes and preserves left/right pivot widths and break mode in the output.
- Labels each result `STRUCTURE_CANDIDATE_NOT_OWNER_FROZEN`; a same-bar dual break is marked ambiguous and aborted.

This is a transparent mechanical candidate interpretation of the supplied protected-swing prose. The pivot widths, close-vs-wick rule, exact definition of “meaningful” structure and independent review process remain unapproved. No candidate from this function is automatically an authorized Protected Swing or trade signal.
