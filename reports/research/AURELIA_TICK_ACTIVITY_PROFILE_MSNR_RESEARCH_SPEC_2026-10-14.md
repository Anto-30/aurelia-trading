# AURELIA Deriv Tick-Activity Profile + MSNR — Research Specification

**Status:** Proposal; research-plane only; not a live-trading approval  
**Date:** 2026-10-14  
**Canonical engine:** `Anto-30/aurelia-trading`, branch `main`  
**Intended use:** Research design for 1-minute triggers and 15-minute context in the existing MSNR strategy path  
**Capital/execution authority:** None

## 1. Decision summary

Do not implement a feature that claims to be true traded-volume Volume Profile from the currently documented Deriv tick-history response. The official `ticks_history` response exposes timestamped prices (and, in candle mode, OHLC candles); the schema does not expose per-trade volume or trade size. See [Deriv Ticks History](https://developers.deriv.com/docs/data/ticks-history/) and [the response schema](https://github.com/deriv-com/deriv-api-schemas/blob/master/schemas/ticks_history_response.schema.json). A histogram of observed price updates is therefore a **tick-activity / price-visit proxy**, not traded volume-at-price.

TradingView itself distinguishes trade volume from tick volume in its [Volume Profile concepts](https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/). That distinction supports a clear data contract; it does not establish that the Deriv feed is equivalent to any particular platform's tick-volume feed.

The existing main-branch research audit says to disable volume profile, CVD, depth, and order-flow features unless the source supports them. This proposal respects that gate:

- **Research-only:** An explicitly named `TICK_ACTIVITY_PROFILE` may be studied on raw Deriv timestamp/price observations. Its POC/VA/HVN/LVN-like levels must be labeled *activity-profile estimates*, never as actual traded-volume levels or proof of liquidity.
- **Trading/runtime:** The feature stays disabled for trading decisions until the data contract is verified, the feature semantics are explicitly approved, the existing MSNR path is extended rather than duplicated, and all research, risk, governance, and instrument gates pass.
- **True Volume Profile:** Enable only if an independently verified adapter/source supplies volume-at-price (or trade records with quantities) with provenance, timestamp semantics, instrument scope, and documented completeness.
- **No capital authority:** Neither this document, an AI proposal, a backtest, nor green CI can modify `config/LIVE_LOCK.yaml`, qualify a strategy, or authorize an order.

This is a specification, not evidence that the feature has been implemented, that the strategy has an edge, or that live trading is ready.

## 2. AURELIA boundaries and integration point

Use the existing single AURELIA engine and existing strategy identity `MSNR_LIQUIDITY_SWEEP` in `config/strategy_registry.json`. Do not create an alternate strategy engine or let Layer 9, an LLM, a research worker, a profile calculator, or an external package submit orders or change capital policy.

Proposed data path:

`Deriv market-data adapter -> immutable raw observations -> validated bars/profile snapshots -> existing MSNR detector -> deterministic feature/confluence result -> Layer 6 risk and instrument-economics validation -> existing authority/release gate`

Layer 9 may calculate research features, design experiments, and explain evidence. It may not approve its own evidence, change production registry status, or promote a candidate. Layer 6 / deterministic authority remains responsible for hard controls. The existing broker adapter and capital plane remain the only route for any separately authorized broker action.

Keep the result types explicit and typed. Do not pass a free-form LLM paragraph as a risk-engine input.

Recommended research feature contract:

- `feature_id`: `TICK_ACTIVITY_PROFILE` or, only after verification, `TRADED_VOLUME_PROFILE`.
- `data_source_kind`: `TICK_PRICE_OBSERVATIONS`, `VERIFIED_TRADE_VOLUME`, or `UNAVAILABLE`.
- `evidence_quality`: `VALID`, `STALE`, `GAPPED`, `TRUNCATED`, `UNVERIFIED_SOURCE`, or `INVALID`.
- `symbol`, `contract/instrument identity`, `timeframe`, `bin_width_ticks`, `anchor_start_time`, `as_of_time`, `source_revision`, `raw_data_hash`, `profile_algorithm_version`.
- `poc_price`, `vah_price`, `val_price`, `node_levels`, `profile_coverage`, `observation_count`, `value_area_fraction`, and the method used to calculate them.
- `semantics_label`: exactly one of `TRADED_VOLUME` or `PRICE_VISIT_ACTIVITY_PROXY`.
- `live_eligible`: false by default; it must not be set by Layer 9 or an LLM.

Reject invalid, stale, truncated, incomplete, mismatched, or unverified inputs. A missing field must not silently become zero, average volume, a synthetic bid/ask spread, or an assumed market microstructure value.

## 3. Data semantics and integrity requirements

### 3.1 Source contract

The current public Deriv `ticks_history` API documents `history.prices` and `history.times`; candle mode returns `open/high/low/close/epoch`. The documented structures do not expose per-tick traded quantity. The collector must record the exact request style, symbol, start/end boundaries, granularity/count, API/schema revision if available, retrieval time, response timestamps, and data hash.

Before calculating even a proxy profile:

1. Validate price/time array lengths, price numeric validity, timestamp bounds and chronology, symbol identity, timezone handling, and tick-size/precision mapping.
2. Detect truncation, gaps, reconnects, overlapping requests, out-of-order timestamps, and response errors. Preserve original observations and provenance. Do not collapse all repeated `(timestamp, price)` pairs globally, since the feed may legitimately publish multiple observations within the same timestamp resolution.
3. Deduplicate only overlaps proven to be the same record across adjacent historical retrieval windows, using a documented deterministic boundary rule.
4. Use integer tick coordinates or decimal-safe quantization; never use binary floating-point equality as the canonical tick identifier.
5. Keep raw source snapshots immutable and content-addressed. Store normalized data separately from the source capture.
6. Mark the profile invalid if required source coverage is missing; never backfill missing observations with fabricated volume.

A volatility correlation check can determine whether the **observed price-update count proxy** covaries with realized volatility. It cannot verify correlation with true traded volume when true volume is not present in the same source. Report those as separate questions.

### 3.2 Explicit modes

| Mode | Meaning | Permitted use |
|---|---|---|
| `VERIFIED_TRADED_VOLUME` | Source provides verifiable quantity/trade volume at price, with documented lineage | Research; live use only after full independent qualification |
| `PRICE_VISIT_ACTIVITY_PROXY` | Histogram counts timestamped observed price updates in each price bin | Offline / paper research only under this proposal |
| `BAR_ACTIVITY_PROXY` | A separately documented vendor field counts updates per bar | Research only; never infer it from OHLC alone |
| `UNAVAILABLE` | No defensible volume/activity input, invalid provenance, or incomplete data | Disable profile-dependent signals |

Do not turn OHLC bars into artificial traded volume by distributing an invented equal quantity across the high-low range. If only OHLC is available and no vendor activity field is exposed, this feature is `UNAVAILABLE`.

Do not claim CVD, buy/sell aggressor volume, delta, footprint, DOM, resting liquidity, participant identity, maker/taker volume, or true liquidity vacuums from timestamped price updates alone.

## 4. Profile calculation specification

### 4.1 Observation window and anchor

Use the current, deterministic MSNR implementation and its confirmed-swing logic as the source of anchors; do not fork a second MSNR detector solely for profiling. An anchor may only become usable at the timestamp when the existing swing/structure logic confirms it using information actually available then. Its historical pivot timestamp can be earlier, but the feature's publication/availability timestamp must remain the confirmation time.

For each as-of decision time (t):

- Use only source observations with timestamps at or before the permitted cut-off. For a signal derived from a completed candle, compute the signal after that candle has closed, and simulate entry no earlier than the next eligible observation after modeled latency.
- Define anchor start, end/as-of time, session/day boundary, and included/excluded endpoints explicitly.
- Do not use a future swing endpoint, future VAH/VAL, future POC, or final session profile for an earlier decision. An expanding profile anchored to a confirmed prior swing may update only using observations that have arrived by the current as-of time.
- Store the exact anchor IDs and the confirmation times in each profile snapshot. If anchors change, record a new version; do not rewrite prior emitted signals.
- Use UTC timestamps internally and retain the source epoch. Any session segmentation must be instrument-specific. Do not apply London/New York cash-session assumptions to Deriv synthetic indices without verified justification.

### 4.2 Price bins and Point of Control

Use verified instrument tick size and a preregistered bin width expressed as an integer number of ticks. Map each valid observation to a deterministic integer bin. Do not choose bin widths by looking at the held-out test set.

For the proxy, the row statistic is **count of observed price updates in the bin**, not traded volume. The proxy POC is the bin with the highest observed count. Deterministic tie-breaking must be specified and tested (for example, lower-price bin first); it may not depend on the trade direction or future price movement.

For verified trade volume, aggregate the actual volume quantities to the same bins and label the result `TRADED_VOLUME`.

### 4.3 Value Area, VAH and VAL

The target area fraction defaults to 70% for comparability, but the algorithm version and result must record the chosen value. Start with the POC bin, then expand to the adjacent lower- or higher-price bin with the larger row quantity until the cumulative quantity meets/exceeds the target fraction. Specify a deterministic tie rule. This creates a contiguous value area. Do not silently select the top 70% of disconnected rows and call the result the same method.

For `PRICE_VISIT_ACTIVITY_PROXY`, output `activity_poc`, `activity_vah`, and `activity_val`, or ensure every consumer carries the proxy semantics label. Do not report them as real market-volume POC/VAH/VAL.

Test invariants: POC is an included bin; VAL ≤ POC ≤ VAH; VAH/VAL are valid bin boundaries; included row quantity reaches the target fraction; deterministic ties produce identical output; prefix-only recalculation does not change previously emitted snapshots.

### 4.4 HVN/LVN-like nodes

Do not infer tradable liquidity from a peak or trough in observed update counts. If research needs node features, name them `ACTIVITY_HIGH_NODE` and `ACTIVITY_LOW_NODE` for the proxy. Any node detector must be deterministic and preregistered: smoothing window, prominence/minimum separation, and edge handling must be frozen before untouched OOS testing. Include these parameters in the profile hash. Avoid manually selected nodes or chart-by-chart interpretation that cannot be replayed.

A proxy low-count region says only that fewer source price updates landed in those bins during the chosen observation window. It does **not** establish thin order-book depth, small slippage, a liquidity vacuum, or the speed of a future move. Slippage and transaction costs must be measured independently from the actual supported execution/contract product.

## 5. Timeframe and MSNR confluence model

The intended layout is **15-minute completed-bar context + 1-minute execution trigger**. Both feature snapshots and MSNR signals must obey a strict as-of timestamp contract. The 15-minute data establishes the current structural regime; the 1-minute data refines the trigger. A 1-minute proxy profile is noisy and must not override a conflicting higher-timeframe structural state by itself.

Reuse the existing MSNR functions and output types. Confirm their actual implementation and behavior before mapping confluence conditions. Where the current implementation does not define a condition, add a separately reviewed deterministic definition instead of allowing an LLM to improvise it.

Test three hypothesis families separately:

1. **Value-boundary rejection + MSNR structure shift.** Price tests or briefly crosses a pre-existing VA boundary and closes back within the area; a confirmed MSNR shift occurs within a preregistered number of completed 1-minute bars. Test long and short cases separately and distinguish proxy activity levels from verified volume levels.
2. **Breakout acceptance + retest.** A completed 15-minute bar closes outside a previously known value area. A subsequent 1-minute retest and close confirms continuation under a frozen rule. Avoid using the breakout candle's eventual high/low or a value area that includes the breakout itself to make the earlier signal appear cleaner.
3. **Low-activity-region traversal.** Price enters a predefined low-count proxy region with independent momentum/MSNR confirmation. Treat this as a low-confidence research hypothesis, not a liquidity-vacuum setup. Model quote/contract costs and latency pessimistically. The feature remains research-only.

For each family, report profile-only, MSNR-only, combined, and no-profile baselines. If the combined strategy does not outperform a fair MSNR-only baseline after costs and uncertainty, reject the added feature even if its stand-alone chart examples look persuasive.

### 5.1 Signal conditions must be machine-readable

A signal record should contain:

- strategy/feature IDs and versions;
- instrument/product ID and verified tick size;
- profile window, anchor IDs, algorithm version and semantics label;
- last completed 15-minute and 1-minute bar timestamps;
- MSNR setup type and confirmed structure IDs;
- side, setup family, entry trigger rule, invalidation condition and expiry rule;
- profile value/node relationship as known at signal time;
- source data hash and evidence-quality state;
- estimated costs, fill/entry model, payoff model, and the reason the setup was accepted or rejected.

The signal must be reproducible from the raw input and frozen configuration. Natural-language analysis is explanatory metadata, not the executable condition.

## 6. Entries, stops, targets and Deriv product compatibility

Do not emit a live-ready numeric entry, stop-loss or take-profit merely from profile geometry. Levels must be derived from the verified instrument tick size and data actually available at the decision time, then tested with the supported product's payoff model.

For a supported linear price instrument, research can evaluate:
- entry at a next-observation/next-bar rule after completed-signal confirmation;
- structural invalidation beyond a confirmed swing or other preregistered price boundary;
- fixed-risk targets such as a prior known POC/VA boundary or node;
- actual spread, commissions/fees, slippage, quote latency and adverse fills.

Those are price-path hypotheses, not permission to transmit orders. Stop/target collision in OHLC-only data is ambiguous and must be handled conservatively; do not award the favorable outcome when ordering cannot be known.

AURELIA's documented canonical Deriv path is the Options API, including verified contract/product details and proposal/payout. If the intended product is a purchased fixed-payout contract, a price crossing a hypothetical stop or target does not imply the contract was closed there. Treat the stake / supported contract terms as the actual maximum-loss and payoff basis, and use observed contract outcomes and proposal prices. Report profile price levels as analytical context only unless the selected product demonstrably supports the required exit order and the adapter is verified for that order type.

For fixed-payout contracts, do not use the linear formula ((TP-entry)/(entry-SL)) as if it were the realized trade R-multiple. Compute results from the real contract payoff model: net realized P&L after applicable costs divided by the preregistered risk budget / maximum loss, with the precise denominator reported. Validate the contract, duration/expiry, quote timestamp, purchase price, payout and settlement semantics against actual Deriv response fields. Unknown product mapping or payout economics => `INSTRUMENT_ECONOMICS_UNVERIFIED` and no qualification.

Do not invent the spread threshold X. If the instrument/feed exposes an independently verifiable spread, use a preregistered instrument-specific threshold. If not, set spread to `UNAVAILABLE` and reject any spread-dependent rule, or use a separately validated product-specific quote-cost guard. Missing spread is not zero spread.

## 7. Layer 6 risk controls — required proposal, subject to existing policy

All controls must be deterministic, testable, and fail closed. Research rules are not a substitute for the existing risk, authority, and release gates.

1. **Input/data guard:** reject stale, gapped, truncated, non-monotonic, out-of-order, invalid-price, wrong-symbol, wrong-account/product, unverified-tick-size, or hash-mismatched profile inputs.
2. **Feature-authority guard:** `TICK_ACTIVITY_PROFILE` cannot authorize or submit trades and stays in offline research/paper mode unless a separate approved policy explicitly permits it.
3. **Missing-cost guard:** reject any candidate whose relevant execution cost, contract payoff, or required spread input is unknown. Never turn unavailable cost into zero.
4. **Daily structural adverse-move circuit breaker:** the requested idea was to halt when a completed 15-minute bar closes beyond a daily value boundary with activity greater than 2× a baseline against open exposure. With current Deriv data, that would be **observed tick count / activity**, not true volume; it must remain a research hypothesis until proxy semantics are approved. Pre-register the baseline window, whether the current bar is excluded from the average, session reset, required source coverage, and exposure direction. When a qualified deterministic breaker eventually triggers, block new entries and emit an audit event. Do not claim it can liquidate an open purchased contract unless a verified contract-management flow and authority explicitly support that action.
5. **LVN/low-count size haircut:** a 50% reduction inside an LVN is not evidence-based by itself and conflicts with the current repository's exact balance-derived stake policy unless implemented as an approved deterministic risk-budget modifier. Do not silently alter the existing stake rule. If policy owners approve a haircut, apply it *before* final Layer 6 sizing and affordability checks; if the reduced amount is below the fresh broker-reported minimum for the exact contract, reject the trade rather than round up or bypass the minimum.
6. **Kill-switch and max loss:** existing daily drawdown, consecutive-loss, per-trade maximum-loss, exposure, account-isolation, reconciliation, and kill-switch rules take precedence. This feature may tighten risk but never relax an existing control.
7. **Probability and qualification:** do not manufacture a win probability from confluence scores. A probability outside the system's allowed interval is rejected, not clipped; in-band values are still blocked if uncalibrated, stale, drifted, economically invalid, or unqualified.
8. **Fail-closed observability:** every accept/reject includes a deterministic reason code, input/profile hash, timestamp, rule version and strategy version. Never log credentials, authenticated URLs or secret-bearing payloads.

## 8. Python backtest and data-validation plan

### 8.1 Data preparation

Implement in the existing research/labs path after the source audit; do not create a second runtime. The collector should:

- fetch bounded Deriv `ticks_history` data with explicit symbol/start/end/count and bounded retry/backoff;
- preserve raw response files and retrieval metadata, recording when API limits may have truncated a range;
- normalize observations to UTC and instrument tick coordinates;
- aggregate 1-minute and 15-minute OHLC from observed ticks for timing/structure only;
- compute a separate count of observed price updates per interval if used for the proxy;
- compute the profile from raw timestamped price updates, not from fabricated OHLC-derived volume;
- expose coverage, gaps, duplicate-boundary handling and source completeness in a validation report;
- verify that each feature snapshot is stable under replay and uses no information after its `as_of_time`.

No market data access, collector success, or schema unit test proves that the data are sufficient for strategy qualification.

### 8.2 Backtest execution semantics

- Use strictly chronological train/validation/OOS splits and purged walk-forward evaluation where labels or holding periods can overlap.
- Freeze anchor, bin-width, value-area, node-detection, MSNR, entry, expiry/exit and cost parameters before untouched OOS evaluation.
- Enforce signal-at-close / entry-after-signal sequencing; do not use a completed bar's high/low to fill an order before its close was known.
- Model the selected instrument/product explicitly. For linear products model bid/ask, spread, fees and adverse slippage if supported and sourced. For fixed-payout options use time-aligned proposal price/payout, stake, expiry and actual contract settlement semantics. Unknown production costs keep net economics incomplete.
- Apply conservative fill and collision rules, API delays, quote staleness, gaps and rejected/unavailable quotes.
- Never let a paper fill, hypothetical price target, public feed replay or synthetic test stand in for real broker evidence.

### 8.3 Required experiments

Report each setup family by instrument, timeframe, side, session/day regime, and position relative to the known profile:

- inside value area;
- outside VAH;
- outside VAL;
- activity/volume POC test;
- VAH rejection and VAL rejection;
- accepted breakout/retest;
- high-count node vs low-count region (only with explicit semantics);
- MSNR-only, profile-only, and combined;
- no-profile baseline; and
- cost sensitivity / ablation results.

Use identical candidate timestamps and execution assumptions for fair comparisons. Avoid choosing the best strategy from non-comparable data or changing thresholds after viewing OOS results.

### 8.4 Required metrics

At minimum, report sample count and coverage, win rate, mean/median net expectancy, net P&L, profit factor, drawdown in equity and R terms, average win/loss, R-multiple distribution, tail loss, exposure/time in market, rejection/fill rate, turnover, latency sensitivity, and results by regime.

For positive realized net trades (P_i) and negative realized net trades (L_i):

- `profit_factor = sum(P_i) / abs(sum(L_i))`;
- `net_expectancy = mean(net_trade_PnL)` and also mean net R under a clearly stated risk denominator;
- `max_drawdown` is computed on the chronological marked-to-model equity series, with its convention stated.

Use confidence intervals / block bootstrap or another dependence-aware uncertainty method, and report the number of independent days/regimes as well as trade count. Do not present a win rate, a high R-multiple on a small sample, or a PF threshold alone as evidence of a durable edge.

A PF below 1.2 after realistic costs is a rejection/screen-out under the proposed user criterion. PF ≥ 1.2 is **not** a pass by itself: positive out-of-sample expectancy with uncertainty analysis, robustness, calibration, adequate sample, and full product-cost validation still have to pass. Do not invent a historical expected win rate or PF in reports before the backtest has run.

## 9. Test plan and acceptance criteria

### Deterministic unit/property tests

- price-to-bin quantization for decimal FX prices, integer synthetic-index ticks, and tick-size boundary cases;
- empty, malformed, stale, gapped, truncated, out-of-order, duplicate-boundary and mismatched-symbol data;
- value-area target fraction, contiguous expansion, tie handling, POC inclusion and VA bounds;
- node detection determinism and fixed parameters;
- no-lookahead: appending future ticks cannot alter any prior snapshot/signal;
- swing confirmation timing and as-of profile end point;
- same raw inputs + versioned parameters always produce identical serialized results and hash;
- timeframe alignment: only completed 1-minute/15-minute bars affect the corresponding decision;
- no entry on signal bar; first eligible fill occurs after modeled latency;
- missing bid/ask, proposal, payout, spread, tick size or cost fields yield explicit rejection, not default zero;
- no live eligibility for `PRICE_VISIT_ACTIVITY_PROXY`;
- risk-haircut proposal cannot bypass account balance sizing, broker minimum, probability, exposure, circuit breakers or `LIVE_LOCK`;
- fixed-payout contract outcomes use actual payoff semantics and not price-path stop/target assumptions.

### Integration/replay tests

- compare raw tick replay with repeated-window retrieval and reconnection scenarios;
- record input/output hashes, code/config revision and data coverage;
- replay adversarial cases around VA boundaries, profile re-anchoring, DST/session changes, flat/tied profiles, rapid price updates and high-latency quote responses;
- verify every reject path is fail-closed and emits an auditable reason;
- run the existing assurance and runtime suites on the exact resulting commit and review their output. Source inspection or documentation alone is not a test pass.

### Research acceptance gate

The feature remains `RESEARCH_ONLY_UNQUALIFIED` unless all applicable criteria are evidenced:

- data and instrument/product semantics are independently verified;
- profile algorithm and MSNR integration are deterministic, versioned and replayable;
- no-lookahead, bar timing and cost/contract models pass tests;
- profile+MSNR is evaluated against MSNR-only and no-profile baselines;
- untouched OOS and walk-forward results survive realistic costs and uncertainty analysis;
- net expectancy is positive and robust across relevant regimes, with no reliance on a single parameter island;
- win-probability calibration and drift monitoring pass if a probability is emitted;
- the relevant feature semantics and any risk modifier receive independent review;
- strategy registry evidence is complete and bound to the exact source revision/data/parameters;
- all normal AURELIA release prerequisites independently pass.

No agent may promote the strategy by changing a JSON status, pasting a report, or observing green CI. Live admission remains the responsibility of existing deterministic governance and the current release-lock process.

## 10. Paste-ready Layer 9 research prompt

> **Role and authority**
>
> Act as AURELIA's institutional quantitative research analyst for the existing `MSNR_LIQUIDITY_SWEEP` research path. Your work is advisory and research-only. You may validate data, calculate deterministic features, design/execute approved offline experiments, and write auditable reports. You must not place orders, request secrets, change the strategy registry's qualification status, edit the live lock, weaken Layer 6 controls, or describe a hypothesis as production-ready.
>
> **First task: verify data semantics**
>
> Inspect the actual adapter schema and captured Deriv payloads before calculating a profile. The documented Deriv `ticks_history` response contains timestamped prices / OHLC candles and does not show traded-volume quantities. Unless the exact source provides independently verified volume-at-price data, set `data_source_kind=TICK_PRICE_OBSERVATIONS` and `semantics_label=PRICE_VISIT_ACTIVITY_PROXY`. Do not call the result traded Volume Profile. Do not infer CVD, aggressor-side volume, order-book depth, liquidity, or slippage from a price-update count. If the only input is OHLC and no verified activity field exists, set the feature to `UNAVAILABLE` and stop profile-based analysis.
>
> **Profile tasks**
>
> For each eligible snapshot, use the confirmed swing/anchor as known at the time, a verified tick size, a frozen bin width and a fixed calculation method. Compute a POC-like highest-count bin and a contiguous 70% activity value area with deterministic tie-breaking. Compute high-/low-count nodes only if a frozen, versioned detector is configured. Record the source semantics, anchor confirmation time, as-of time, observation count, data coverage, raw-data hash, profile algorithm version, and every parameter. Reject stale, gapped, truncated, mismatched or incomplete inputs.
>
> **MSNR and timeframe confluence**
>
> Use closed 15-minute candles for structural context and closed 1-minute candles for trigger evaluation. Reuse the current deterministic MSNR implementation; do not improvise a second engine or use future-confirmed pivots. Separately test (A) value-boundary rejection + confirmed MSNR shift, (B) 15-minute breakout acceptance + later 1-minute retest, and (C) traversal of a low-count activity region with independent confirmation. These are hypotheses, not presumed high-probability setups. Publish signal availability timestamps and do not simulate entry before the first eligible observation after confirmation and modeled latency.
>
> **Instrument/payoff compatibility**
>
> Before proposing an entry, stop, target, R-multiple or expectancy, identify the actual Deriv symbol and exact contract/product. Determine whether price-based stops/targets are enforceable on that product. For a purchased fixed-payout contract, use observed proposal cost, payout, stake, expiry and settlement semantics; treat profile levels as analysis only unless contract documentation and the adapter prove that the intended exit order is supported. If instrument mapping, costs, spread, payout or maximum-loss semantics are unknown, mark economics unavailable and reject qualification. Do not invent a spread threshold or assume missing costs are zero.
>
> **Experiments and metrics**
>
> Run profile-only, MSNR-only, combined, and no-profile baselines on the same chronological signals. Use frozen parameters, time-ordered train/validation/untouched OOS, purged walk-forward where needed, and conservative fills/costs. Segment results by inside/outside value, boundary rejections, POC tests, high-/low-count proxy region, direction, timeframe, symbol and regime. Report trade count, win rate, net expectancy, PF, drawdown, average win/loss, net R distribution, tail risk, costs, latency sensitivity and dependence-aware uncertainty. A PF below 1.2 after realistic costs fails the proposed screen; PF at or above 1.2 is not sufficient for acceptance. Never assert historical win rate or PF without a reproducible result artifact.
>
> **Layer 6 and release behavior**
>
> Emit machine-readable feature/signal evidence plus deterministic reject reason codes. Missing/stale inputs, insufficient coverage, unverified instrument data, missing costs, invalid timing, stale quotes, uncalibrated probabilities or drift must fail closed. Treat the proposed 50% low-count-region risk haircut and the 2× activity-breaker as unapproved hypotheses until reconciled with the current stake policy and independently reviewed. Any approved haircut must precede final deterministic sizing; if it cannot fund the verified contract minimum, reject rather than round upward. Do not use this proxy for live decisions under the current data policy.
>
> **Required output**
>
> 1. Data-source and instrument semantics verdict.
> 2. Input-quality report and exact data/config/code hashes.
> 3. Profile algorithm/method, anchor/as-of timestamps and labeled price levels.
> 4. Deterministic MSNR condition and why the signal is or is not valid.
> 5. Entry/exit *simulation model* and explicit instrument compatibility; no unsupported executable stop/target claims.
> 6. Net metrics, sample size, uncertainty, cost assumptions and baseline/ablation comparison.
> 7. Fail-closed Layer 6 checks, outstanding blockers and exact reason codes.
> 8. Final status: `REJECTED`, `RESEARCH_ONLY_UNQUALIFIED`, or `READY_FOR_INDEPENDENT_REVIEW`. Never return `LIVE_READY` or `AUTHORIZED`; those are controlled by existing deterministic release governance.
>
> Stop and report a blocker instead of filling any material gap with an assumption.

## 11. Required report schema

Every experiment report should include at least:

```json
{
  "schema": "aurelia.tick_activity_profile_experiment.v1",
  "status": "RESEARCH_ONLY_UNQUALIFIED",
  "strategy_id": "MSNR_LIQUIDITY_SWEEP",
  "feature_id": "TICK_ACTIVITY_PROFILE",
  "semantics_label": "PRICE_VISIT_ACTIVITY_PROXY",
  "data_source_kind": "TICK_PRICE_OBSERVATIONS",
  "symbol": null,
  "product_contract_id": null,
  "timeframes": ["15m", "1m"],
  "data_start_utc": null,
  "data_end_utc": null,
  "as_of_cutoff_utc": null,
  "source_schema_revision": null,
  "raw_data_sha256": null,
  "normalized_data_sha256": null,
  "code_revision": null,
  "config_sha256": null,
  "profile_algorithm_version": null,
  "tick_size_source": null,
  "bin_width_ticks": null,
  "anchor_ids": [],
  "observation_count": null,
  "coverage_status": "UNVERIFIED",
  "profile_levels": {
    "poc_or_activity_poc": null,
    "vah_or_activity_vah": null,
    "val_or_activity_val": null,
    "node_levels": []
  },
  "execution_model": "UNVERIFIED",
  "cost_model": "UNVERIFIED",
  "trade_count": 0,
  "net_expectancy": null,
  "profit_factor": null,
  "max_drawdown": null,
  "win_rate": null,
  "uncertainty_method": null,
  "oos_status": "NOT_RUN",
  "calibration_status": "NOT_RUN",
  "independent_reviewer": null,
  "live_eligible": false,
  "reject_reasons": ["DATA_SOURCE_VOLUME_SEMANTICS_UNVERIFIED"]
}
```

Null values represent missing evidence; they must not be replaced by plausible invented values. Update the schema only with a reviewed version change.

## 12. Official/reference sources

- Deriv API — [Ticks History](https://developers.deriv.com/docs/data/ticks-history/)
- Deriv API — [Ticks Stream](https://developers.deriv.com/docs/data/ticks/)
- Deriv API schemas — [Ticks history response](https://github.com/deriv-com/deriv-api-schemas/blob/master/schemas/ticks_history_response.schema.json)
- TradingView — [Volume Profile indicators: basic concepts](https://www.tradingview.com/support/solutions/43000502040-volume-profile-indicators-basic-concepts/)

These references document the publicly described API/charting semantics. They do not establish strategy profitability, a production spread model, or live eligibility.
