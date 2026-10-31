# T4F × 369 Research Specification

- **Document ID:** AURELIA-T4F-369-RESEARCH
- **Version:** 0.1.0-draft
- **Status:** RESEARCH ONLY / NOT FROZEN / NOT EXECUTABLE
- **Scope:** T4F × 369 numerical-level and time-structure framework supplied by the owner on 2026-10-31.
- **Authority:** Documentation and research diagnostics only. No capital or execution authority.

## 1. Governance and interpretation

This document records the supplied framework without asserting that the 369 numerical mapping has predictive value. It does not authorize live trading, paper execution, strategy promotion, or capital access.

- `LIVE_EXECUTION = BLOCKED`
- `capital_plane_mode = VERIFY_ONLY`
- `FINAL_EXECUTION_AUTHORIZATION = false`
- `research_capital_authority = false`

No agent, indicator, strategy module, or research result may override these controls. The 369 levels are attention references only. A projected level is not a trade signal.

## 2. Numerical mapping

Digital-root mapping:

| Digital root | Base step |
|---|---:|
| 1, 4, 7 | 12 |
| 2, 5, 8 | 15 |
| 3, 6, 9 | 18 |

Instrument scaling supplied:

| Instrument | Scale | Research status |
|---|---:|---|
| XAUUSD | 1× | As supplied |
| NQ | 10× | As supplied |
| ES | 1× | Owner says verify per instrument; not independently validated |

For a positive reference price (P), take the integer part (I=\lfloor P\rfloor). Sum the decimal digits of (I), repeatedly reducing to one digit. Map that root to the base step, then apply the instrument scale.

Use the complete original reference price, including decimals, in the projection:

- Bearish from protected high: (L_n=P-nS)
- Bullish from protected low: (L_n=P+nS)

At least four levels are projected. The calculation must retain full precision. Any exchange-tick rounding is a separate display/execution concern and must not silently alter the theoretical level. A production implementation must define how theoretical levels that fall between valid ticks are represented.

Boundary not yet specified: reference prices below 1 produce integer part zero, which has no mapping in the supplied 1–9 table. The implementation must reject such values unless the owner explicitly defines a rule.

## 3. Protected swing and structure

The framework requires a protected swing to be identified only after a structural break:

- Bearish: the initiating swing high is protected after the decline breaks a meaningful prior higher low.
- Bullish: the initiating swing low is protected after the rally breaks a meaningful prior lower high.

A mechanical pivot is not sufficient. The current research utility's pivot detector is only a causal pivot approximation; it does not identify BOS/MSS, validate the significance of the broken level, or establish a protected swing.

Before automated structural classification, the owner must define:
- Pivot/swing algorithm, left/right confirmation bars, and tie handling.
- What makes an opposing high/low structurally meaningful.
- BOS/MSS comparison rule: wick breach or completed candle close.
- Required displacement or confirmation, if any.
- Protected-swing replacement and invalidation rules.
- Timeframe on which the protected swing is established.

Until those are fixed, protected swings must be manually supplied and labeled as human-identified, not algorithmically verified.

## 4. Time structure

The supplied references and phase windows are preserved verbatim:

- 00:00 — True Day Open.
- 02:22 — True London Open.
- London 369: Phase 3 01:25–02:22; Phase 6 02:22–02:56; Phase 9 02:56–03:52.
- London 963: Phase 9 03:52–04:48; Phase 6 04:48–05:23; Phase 3 05:23–06:19.
- New York AM window: 07:20–10:45, with supplied normalized markers 0.000, 0.315, 0.630, 0.810, 1.000.

Directional reference rule, as supplied: price above either opening reference means look for sells; price below means look for buys. This is a directional observation only, not an entry.

**Time arithmetic discrepancy:** the 07:20–10:45 window is 205 minutes. A 0.315 fraction lands at approximately 08:24:35, not 08:30. The 0.630 and 0.810 fractions land at approximately 09:29:09 and 10:06:03. The stated 08:30 marker is therefore inconsistent with the exact 0.315 fraction and must be resolved rather than silently normalized.

Blocking time definitions:
- Timezone for 00:00, 02:22, London windows, and New York window (IANA names).
- Whether opening references use candle open, first quote, or another session definition.
- Day boundary and holiday/early-close treatment.
- Exact boundary inclusion and bar timestamp convention.
- Whether the 369 fractions or approximate clock times control when they differ.
- DST handling, especially weeks when London and New York clock changes are not aligned.
- Missing-bar and feed-gap policy.

All stored timestamps should be UTC with explicit conversion to the approved session timezone. No hard-coded UTC offset or silent nearest-bar substitution.

## 5. M15 interaction and M1 confirmation

At a projected 369 level on M15, classify the interaction as one of:

**Case A — breakout candidate**
- A completed M15 candle body closes beyond the level.
- This is not an entry.
- Proceed to M1 for the required liquidity and structure confirmation.

**Case B — sweep candidate**
- The M15 wick pierces the level and the completed candle body closes back on the original side.
- This is not an automatic reversal.
- Identify the relevant BSL/SSL pool, then wait for M1 market-structure reversal confirmation.
- After confirmation, identify the first aligned FVG.

The exact meaning of “decisive” body break, the minimum distance beyond a level, handling of a candle that pierces both sides, and whether the breakout candle must close directionally remain unresolved.

## 6. M1 reversal and entry model

Bearish candidate sequence:
1. Sweep recognizable buy-side liquidity above a high.
2. Wait for bearish M1 MSS/BOS: break of a prior higher low.
3. Identify the first bearish FVG after confirmation.
4. Plan a sell at the FVG 50% midpoint.
5. Place the stop beyond the FVG high/invalidation point.

Bullish candidate sequence:
1. Sweep recognizable sell-side liquidity below a low.
2. Wait for bullish M1 MSS/BOS: break of a prior lower high.
3. Identify the first bullish FVG after confirmation.
4. Plan a buy at the FVG 50% midpoint.
5. Place the stop beyond the FVG low/invalidation point.

The following definitions are required before coding:
- Recognizable liquidity pool and equal-high/equal-low tolerance.
- Swing algorithm used for the M1 structure break.
- Exact BOS/MSS candle-close rule.
- FVG three-candle definition, minimum gap size, and treatment of overlapping gaps.
- “First FVG” ordering and expiry.
- Whether price must touch the exact midpoint or may fill through it.
- Entry order type, expiry, spread treatment, and missed-fill policy.
- Exact stop buffer, tick rounding, gap-through-stop handling, and same-bar stop/target ordering.

The supplied prompt states CISD is essential. Its definition (“breaks structure in intended direction with displacement”) overlaps with the M1 MSS/BOS requirement but does not specify whether CISD is a separate condition. Do not double-count or omit it: define whether CISD is the same event, a stricter additional filter, or a separate confirmation.

## 7. SMT and correlated markets

For NQ/ES, the supplied SMT rule is:
- NQ lower low without ES lower low → bullish divergence.
- NQ higher high without ES higher high → bearish divergence.
- Observation window: 09:27–09:33 New York time.

Blocking definitions: exact comparison swing, matching time window, tolerance for asynchronous highs/lows, data source and timestamps, and whether the divergence is required or optional. SMT is unavailable if either feed is missing, stale, or not time-aligned. Do not substitute one instrument's feed for the other.

## 8. STDV expansion targets

The supplied target ratios are 38.2%, 61.8%, 100.0%, and 161.8%.

The anchor and measurement range are not defined. Before calculation, specify:
- Which swing, impulse, range, or entry-to-stop distance defines 100%.
- Direction/sign convention for long and short.
- Whether targets are measured from entry, FVG, sweep extreme, or another anchor.
- Whether targets are fixed at entry or can be recalculated.
- Partial-exit and final-exit rules.

Until then, these are labels only; no target prices or R:R may be fabricated.

## 9. Backtest design and metric integrity

The proposed comparison is:
- Full T4F × 369 system.
- Structure-only control with the same structure, liquidity, M1 confirmation, FVG, stop, target, fill, and cost rules but without the 369 level filter.

The supplied material contains conflicting sample suggestions: 100 trades minimum per arm in the narrative, but 50 total (25 per arm) in the action plan. The 25-per-arm proposal is not adequate as a decision threshold. Pre-register a minimum of 100 eligible trades per arm as a preliminary descriptive floor, then determine power/uncertainty from observed variance; 100 trades does not by itself establish statistical significance.

Comparison requirements:
- Same instrument, session, time window, data source, costs, and chronological partitions.
- Freeze swing-selection and all signal rules before viewing outcomes.
- No retrospective manual selection of swings to align levels with reversals.
- Report all registered variants, rejected events, missed fills, and no-trade periods.
- Use chronological train/validation/untouched OOS; no OOS-driven tuning.
- Include spread, commission, slippage, financing where applicable, and conservative intrabar collision rules.
- Report net expectancy in R, profit factor, drawdown, trade count, win rate, average win/loss, exposure, and uncertainty.
- Use paired comparisons on matched eligible events where possible; do not compare unrelated samples.

A level-touch hit rate is not a profitability metric. The supplied “discard if Level 1/2 hit rate is below 40%” rule is unsupported: touches do not establish reversal, entry fill, stop placement, target achievement, or positive net expectancy. Do not use that threshold as a promotion or rejection gate.

## 10. Supplied code audit

### TradingView Pine projector
The submitted indicator is a manual level projector. It does not detect protected swings, BOS/MSS, time phases, liquidity, FVG, CISD, SMT, or trade entries. The repository version deletes prior drawings before recreating them on the last bar, avoiding the original line/label accumulation defect. It remains a visual aid only. ES step scaling is marked unverified.

### Python level research utility
The repository utility computes digital roots and level projections, validates basic candle fields, detects causal mechanical pivots, scans future level touches, and calculates descriptive metrics. It is not a complete T4F backtester and does not simulate M15/M1 structure, FVG midpoint fills, stops, STDV targets, costs, or actual trades.

Known review items before relying on the utility:
- Candle gap validation needs exact interval/session semantics; gaps must not silently pass.
- Pivot detection currently hardcodes a 60-second interval and only rejects duplicate/out-of-order timestamps, not all quality failures.
- Touch scanning needs to verify the pivot/projection reference binding and input data quality.
- Metric inputs need explicit chronological and trade-integrity validation.
- Floating-point levels need a documented tick-rounding/display policy.
- Prices with integer part zero must fail explicitly until a mapping is defined.

### Supplied Deriv fetcher
The supplied fetcher calls `run_forever()` before sending its request. That call blocks until the connection closes; the subsequent send is therefore not a valid connected-session request. The request must be sent from an `on_open` callback, with a request ID, timeout, response/error validation, and deterministic close. The code also uses the legacy Binary WebSocket v3 host, which the repository README marks diagnostic-only; it must not become a production fallback. No historical data retrieval or backtest is claimed by this draft.

## 11. Readiness and blockers

**Current status: NOT READY FOR STRATEGY BACKTEST OR EXECUTION.**

Required before a deterministic full-system backtest:
1. Resolve all timezone/session and 0.315-marker ambiguities.
2. Freeze protected-swing/BOS/MSS and liquidity-pool definitions.
3. Freeze M15 breakout/sweep classification and all M1 confirmation rules.
4. Freeze FVG, CISD, entry, stop, STDV target, and fill/cost models.
5. Define SMT feed synchronization for NQ/ES.
6. Obtain genuine source-bound OHLC data and validate continuity/session gaps.
7. Register the full and structure-only experiments, partitions, and trial count.
8. Implement unit/property tests for boundaries, DST, gaps, pivots, structure, FVG, fills, stops, and target collisions.
9. Independent review and immutable spec/code/data hashes.

**Final disposition:** research documentation and visual level projection only. No empirical edge is established. No strategy is frozen or qualified. All AURELIA capital and live-execution locks remain unchanged.
