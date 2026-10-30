# 3-6-9 MSNR Experimental Specification

- **Document ID:** AURELIA-MSNR-EXP-SPEC
- **Version:** 0.1.0-draft
- **Status:** EXPERIMENTAL / FOR REVIEW / NOT FROZEN
- **Created:** 2026-10-30
- **Repository baseline:** `main` at `d04564aca0648201feff0326fe9af0fbcee92e94`
- **Authority:** Research documentation only. No capital or execution authority.

## 1. Purpose and scope

This document records the user's selected research hypotheses for the 3-6-9 MSNR framework. It defines the currently agreed experimental architecture, separates alternatives that must be tested independently, and identifies unresolved parameters that prevent a deterministic implementation from being called frozen.

It does **not** authorize a backtest using guessed parameters, strategy promotion, paper/live execution, or capital access. Numerical values not explicitly selected below remain unspecified.

## 2. Governance invariants

The following controls are immutable for this work:

| Control | Required value |
|---|---|
| `LIVE_EXECUTION` | `BLOCKED` |
| `capital_plane_mode` | `VERIFY_ONLY` |
| `FINAL_EXECUTION_AUTHORIZATION` | `false` |
| `research_capital_authority` | `false` |
| Candidate qualification | `REJECTED / UNQUALIFIED` pending new evidence and review |

No agent, strategy module, test harness, configuration, or research result may override these controls. Missing or ambiguous inputs must fail closed. No live credentials, order submission, or capital authorization are in scope.

## 3. User-selected experimental hypotheses

| Dimension | Selected hypothesis | Status |
|---|---|---|
| Phase 6 reference | Previous range over 20 completed candles | Selected; exact bar indexing still to formalize |
| Sweep confirmation | Candle closes back inside the previous range | Selected; exact equality and multi-bar handling unresolved |
| Layer 9 displacement | Test candle-body and full-candle-range measures as separate models | Selected |
| ATR reference period | Test ATR(14) and ATR(20) as separate models | Selected; estimator and timeframe unresolved |
| Structural target | Compare opposing range boundary, next confirmed opposing swing, and opposing liquidity pool independently | Selected; each target's detection algorithm unresolved |
| Confirmation deadline | Test separate confirmation windows | Selected; window candidates and expiry semantics unresolved |
| Time anchor | 08:50 America/New_York | Selected; exact candle interval and event/confirmation semantics unresolved |
| Exit architecture | Structural invalidation | Selected; swing/invalidation and stop-buffer definitions unresolved |

These are **research selections**, not frozen rules. Do not infer that 20 bars, ATR(14), ATR(20), or 08:50 are proven optimal.

## 4. Phase 6: previous-range liquidity event

### 4.1 Reference range

For a candidate signal candle indexed by (t), use the preceding 20 completed candles, excluding candle (t):

```text
RANGE_HIGH(t) = max(high[t-20], ..., high[t-1])
RANGE_LOW(t)  = min(low[t-20],  ..., low[t-1])
```

The data must be strictly chronological, timezone-aware, and validated for OHLC consistency. The 20-bar reference must not include the signal candle or any future candle.

### 4.2 Sweep and close-back-inside hypothesis

Let `delta` be the minimum sweep excursion. Its value and unit are unresolved.

Bullish candidate:
```text
low[t] < RANGE_LOW(t) - delta
and close[t] > RANGE_LOW(t)
```

Bearish candidate:
```text
high[t] > RANGE_HIGH(t) + delta
and close[t] < RANGE_HIGH(t)
```

This is a proposed formalization of the selected “sweep then close back inside” hypothesis. It is not yet a frozen signal rule.

Unresolved:
- `delta`: absolute price, ticks, or volatility-normalized distance; instrument tick-size source.
- Strict versus inclusive comparisons at the boundary.
- Whether a single candle must both sweep and reclaim, or whether a reclaim may occur in a later candle.
- Maximum sweep-to-reclaim delay if multi-candle reclaim is permitted.
- Treatment of a candle sweeping both boundaries.
- Whether the reclaim candle must also close directionally (bullish close for long / bearish close for short).
- Whether local structure confirmation is required in Phase 6 or reserved for Layer 9.
- Whether multiple sweeps of the same reference range create one event or multiple events.
- Whether a new reference range is computed after a sweep, and the reset rule.

Until resolved, ambiguous/two-sided events and missing tick-size metadata must be rejected rather than guessed.

## 5. Time anchor: 08:50 America/New_York

Use the IANA timezone identifier `America/New_York`; do not hardcode a UTC offset. Store source timestamps in UTC and derive the local session marker with a timezone database that handles daylight-saving transitions.

Unresolved time semantics:
1. Does “08:50” identify the candle opening at 08:50:00 or the candle closing at 08:50:00?
2. Is the sweep required before the marker, on the marker candle, or may it occur in a defined preceding window?
3. Is the marker the Phase 6 event time, the confirmation time, or merely an observation/eligibility time?
4. What happens on missing bars, feed gaps, early closes, or session holidays?
5. Is the rule applicable to Deriv synthetic instruments (which trade continuously) and US equities (with exchange-specific sessions) identically?

No nearest-bar substitution or DST normalization may silently shift the event. The policy for absent marker bars must be explicit and logged.

## 6. Layer 9: displacement model family

Layer 9 is a confirmation layer after a qualifying Phase 6 event. The selected experiment compares two distinct displacement numerators and two ATR periods. Do not collapse them into one blended score.

For a completed candidate displacement candle (t), define:

### 6.1 Model BODY

```text
BODY_DISPLACEMENT(t) = abs(close[t] - open[t]) / ATR_period(t-1)
```

### 6.2 Model FULL_RANGE

```text
RANGE_DISPLACEMENT(t) = (high[t] - low[t]) / ATR_period(t-1)
```

### 6.3 ATR variants

Evaluate `ATR(14)` and `ATR(20)` as separate variants, producing at least these four independent model configurations:

- BODY / ATR(14)
- BODY / ATR(20)
- FULL_RANGE / ATR(14)
- FULL_RANGE / ATR(20)

ATR is referenced using information available before the displacement candle to avoid including the candidate candle in its own normalizer. However, the ATR estimator (Wilder/RMA, SMA of true range, or another explicitly specified estimator), input timeframe, initialization/warm-up, and missing-bar treatment remain unresolved. This lagged-ATR convention is a proposed anti-leakage control and requires review before freezing.

Direction must agree with the Phase 6 hypothesis:
- Long: `close[t] > open[t]`
- Short: `close[t] < open[t]`

A zero-body candle cannot confirm direction. For FULL_RANGE, the range ratio alone is non-directional; the directional close condition above is therefore required.

Unresolved Layer 9 parameters:
- Minimum displacement threshold `theta` for each variant.
- Whether a close beyond a defined structural level is additionally required.
- Definition and lookback for that structural level.
- Whether wick/body proportions, gap conditions, or consecutive candles are filters.
- Whether FVG/iFVG is required, optional, or excluded.
- Maximum confirmation delay after Phase 6.
- Whether the first valid displacement confirms the event or later confirmations can supersede it.
- Whether a displacement candle may also be the Phase 6 sweep/reclaim candle.
- Whether failed/contradictory displacement permanently invalidates the event.

No threshold is assigned in this draft. A threshold must be specified before a deterministic test run; it must not be selected by inspecting the reserved OOS results.

## 7. Confirmation-window experiment

The user selected testing separate confirmation windows but did not select numerical windows. Therefore, the candidate window set is **TBD / REVIEW REQUIRED**.

For every registered window (W), define its start event, end event, candle counting convention, and expiry behavior before implementation. All windows must be evaluated as separate, pre-registered variants on identical eligible events and data partitions.

Do not silently choose “1, 3, 5 candles” or any other values. Record every tested window, including unsuccessful variants, to control multiple-testing and selection bias.

## 8. Structural exit model family

The selected exit architecture is structural invalidation. The three target hypotheses must be tested independently, not combined or selected trade-by-trade after observing outcomes.

### Target A — opposing previous-range boundary

- Long target: the applicable prior-range high.
- Short target: the applicable prior-range low.

Unresolved: whether the target uses the range frozen at Phase 6, the range at entry, or a later refreshed range; behavior if target is already crossed or too close at entry.

### Target B — next confirmed opposing swing

- Long target: next confirmed swing high above entry.
- Short target: next confirmed swing low below entry.

Unresolved: exact pivot/fractal definition, left/right confirmation bars, confirmation delay, minimum prominence, and handling when no qualifying swing exists. A swing cannot be used before it is confirmed using only then-available bars.

### Target C — opposing liquidity pool

Use a separately defined and observable algorithm to identify the next opposing liquidity pool. “Liquidity pool” is not yet operationally defined.

Unresolved: equal-high/equal-low tolerance, clustering window, minimum touches, freshness/mitigation, distance threshold, and whether OHLC-only proxies are acceptable. No DOM, true order-flow, or volume claims may be inferred from OHLC.

### Structural stop / invalidation

The exact invalidation structure is unresolved. The implementation must define:
- Which swing or range level invalidates a long and a short.
- Swing confirmation algorithm and confirmation delay.
- Stop buffer unit and value.
- Whether stop is fixed at entry or can trail.
- Whether/when break-even or partial exits are permitted.
- Handling of gaps and slippage through the stop.
- Whether a stop may be widened (default: no; any exception requires explicit approved rule).

The stop level must be known at entry and may not be retrospectively changed.

### Time exit and execution ambiguity

No time-based exit has been selected. Specify whether positions can remain open indefinitely, expire at a session boundary, or close after a maximum holding period. Also specify:
- Entry fill convention and signal-to-entry delay.
- Spread, commission, slippage and gap model by instrument.
- Same-candle stop/target collision policy (conservative stop-first unless finer data resolves path).
- Partial fills, rejected orders, and missing bars.
- Maximum concurrent positions and duplicate-signal suppression.

## 9. Experimental design and model registry

At minimum, register each unique combination of:
- Displacement numerator: BODY or FULL_RANGE.
- ATR period: 14 or 20.
- Confirmation window: each explicitly approved value.
- Target model: A, B, or C.
- Any later approved threshold or filter variant.

This creates a factorial family. The total number of trials must be counted and recorded before results are inspected. Do not report only the best-performing combination without disclosing all tested variants.

Phase 6-only should be maintained as a separate baseline. Phase 6 + Layer 9 variants must share the same event definitions and data partitions where comparisons are made. Any additional Phase 3 filter must be separately identified; do not silently add it to this specification.

## 10. Data, provenance, and evaluation gates

Before empirical evaluation:
1. Obtain genuine, instrument-specific 1-minute OHLC data from the declared source. Do not substitute synthetic/generated data.
2. Record instrument identifier, venue/feed, timezone, retrieval time, date range, timeframe, source request parameters, and any API/schema version.
3. Validate timestamp uniqueness, strict ordering, expected continuity/session gaps, OHLC consistency, and missing values.
4. Hash the raw payload and canonical final Parquet artifact with SHA-256.
5. Freeze the exact strategy specification, code commit, dependency lock, configuration, and dataset manifest.
6. Establish instrument-specific spread, commission, slippage and gap assumptions from defensible evidence.
7. Pre-register chronological train/validation/OOS partitions and prohibit OOS-driven tuning.
8. Report event counts, rejected events, trade counts, net expectancy, profit factor, drawdown, R-multiples, costs, and uncertainty. Metrics must come from executed code and preserved artifacts.

No empirical performance claim is made by this document.

## 11. Remaining decisions required before SPEC freeze

The following are blocking questions, not implementation defaults:

| ID | Blocking ambiguity | Required resolution |
|---|---|---|
| P6-01 | Sweep excursion `delta` and unit | Explicit value/formula and verified instrument tick size |
| P6-02 | Single-candle vs multi-candle reclaim | Exact state machine and maximum reclaim delay |
| P6-03 | Two-sided and repeated sweeps | Deterministic event de-duplication/invalidation |
| TIME-01 | 08:50 candle open vs close | Explicit timestamp convention |
| TIME-02 | Sweep window relative to 08:50 | Exact eligible event interval |
| TIME-03 | Missing marker candle | Fail-closed behavior |
| L9-01 | ATR estimator/timeframe/warm-up | Exact formula and initialization |
| L9-02 | Displacement threshold(s) | Pre-registered threshold per variant |
| L9-03 | Structural break requirement | Exact level and close/wick rule |
| L9-04 | FVG/iFVG role | Required, optional filter, or excluded |
| L9-05 | Confirmation windows | Explicit list and counting convention |
| EXIT-01 | Structural stop reference | Exact swing/range invalidation algorithm |
| EXIT-02 | Stop buffer | Value, unit, and rounding |
| EXIT-03 | Target A range snapshot | Freeze-at-event vs freeze-at-entry vs refresh |
| EXIT-04 | Target B swing definition | Pivot algorithm and confirmation delay |
| EXIT-05 | Target C liquidity definition | Pool construction and eligibility |
| EXIT-06 | Time exit | Explicit maximum holding/session policy |
| EXEC-01 | Entry/fill/collision model | Exact fill and conservative intrabar rules |
| DATA-01 | Instrument/feed/timeframe | Exact identifier and source |
| COST-01 | Costs | Measured/defensible spread, commission, slippage, gap model |

## 12. Versioning and change control

- **0.1.0-draft (this document):** records selected hypotheses and unresolved questions. Not executable as a frozen strategy.
- **0.2.0-review:** may be prepared after all blocking mathematical definitions are resolved and reviewed. Still not automatically frozen.
- **1.0.0-frozen:** only after explicit owner approval, immutable spec hash, code/config binding, and independent review. Any substantive rule change requires a new version and hash.
- Never edit a frozen version in place. Preserve prior versions and their associated test results.

## 13. Acceptance checklist for independent review

- [ ] All P6, TIME, L9, EXIT, EXEC, DATA and COST blockers resolved.
- [ ] Formula definitions include boundary/equality semantics.
- [ ] No future-bar or unconfirmed-pivot leakage.
- [ ] Every model variant and trial count registered before evaluation.
- [ ] Instrument and source compatibility independently verified.
- [ ] Costs and fill assumptions justified.
- [ ] Unit/property tests cover boundaries, gaps, DST, ambiguous sweeps, expiry and stop/target collisions.
- [ ] Data, configuration, code and outputs are hash-linked.
- [ ] Chronological untouched OOS evaluation completed only after prerequisites are satisfied.
- [ ] Independent reviewer signs off.
- [ ] Governance locks remain unchanged.

**Current disposition:** DRAFT FOR REVIEW. Specification incomplete. No backtest authorization, no strategy qualification, no capital authority, and no live execution.
