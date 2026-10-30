# MSNR Implementation Compatibility Audit

- **Document ID:** AURELIA-MSNR-COMPAT-AUDIT
- **Version:** 0.1.0
- **Status:** READ-ONLY REVIEW NOTE
- **Reviewed source ref:** `main`
- **Source file:** `research/labs/deterministic_intraday_strategies.py`
- **Source blob:** `2398eae6d762e6cdc7a09d2327b379d9c65ae02c`
- **Related specification:** `MSNR_3-6-9_EXPERIMENTAL_SPEC_v0.1.0.md`
- **Execution performed:** Source inspection only. No code executed, no tests run, no backtest run.

## 1. Executive finding

The existing `MSNR_LIQUIDITY_SWEEP` detector is a research-only prototype. It is not an implementation of the newly documented 3-6-9 experimental family. Its current defaults and event logic differ from the user's selected hypotheses in important ways. It must not be treated as the frozen strategy or used to claim empirical validation of the new specification.

## 2. Observed current prototype behavior

The source currently defines:
- `lookback_bars=20`
- `min_sweep_ticks=1.0`
- `stop_buffer_ticks=1.0`
- `max_reclaim_bars=3`
- `require_volume_pop=False`
- `volume_pop_multiplier=1.5`
- regime allowlist `TRENDING_LOW_VOL` and `RANGING_LOW_VOL`
- version string `msnr-v1`

The detector:
1. Requires a caller-supplied tick size.
2. Computes a reference high/low from the lookback candles preceding each candidate sweep candle.
3. Uses inclusive sweep comparisons (`<=` and `>=`) with a one-tick default excursion.
4. Permits a reclaim/confirmation to occur after the sweep, within a maximum three-bar scan.
5. Requires the final supplied candle to close back inside the reference boundary and also break the immediately preceding candle's high/low.
6. Skips two-sided/ambiguous sweeps.
7. Uses the opposing reference-range edge as its only target mode.
8. Uses the sweep extreme plus/minus a fixed tick buffer as its stop reference.
9. Applies a regime classifier/allowlist before producing a candidate.
10. Emits next-bar-open entry timing and explicitly sets capital authority and order submission permission to false.

## 3. Compatibility matrix

| New selected hypothesis | Existing prototype | Compatibility |
|---|---|---|
| Previous range = 20 candles | Default lookback 20 | Partial: same default, but no 3-6-9 version binding |
| Close back inside previous range | Reclaim close inside required | Partial: reclaim can be later than sweep; also requires local structure break |
| BODY and FULL_RANGE displacement models | No Layer 9 displacement calculation found in inspected source | Missing |
| ATR(14) and ATR(20) independent variants | No ATR calculation found in inspected source | Missing |
| Three independent structural targets | Only opposing reference-range edge | Missing |
| Separate confirmation windows | Single configurable max reclaim window, default 3; no registered experiment family | Missing |
| 08:50 America/New_York marker | No marker handling in inspected detector | Missing |
| Structural invalidation | Sweep extreme +/- fixed tick buffer | Partial; not a general structural stop model |

## 4. Material implementation risks

- Reusing this detector unchanged would silently import prototype assumptions (one-tick sweep, three-bar reclaim, local structure break, regime filter, fixed sweep-extreme stop).
- The regime allowlist could materially alter the event population and must be either explicitly included as a separately registered filter experiment or excluded from the baseline. It must not be silently carried over.
- The current function returns one candidate and does not implement the factorial BODY/FULL_RANGE × ATR(14)/ATR(20) × confirmation-window × target-model comparison.
- The current code's target is a reference-range edge; it does not implement the confirmed-swing or opposing-liquidity-pool targets.
- The code's `max_reclaim_bars` is not interchangeable with a Layer 9 displacement confirmation deadline. These are distinct event transitions and need separate clocks.
- No execution or backtest evidence is created by this source inspection.

## 5. Recommended implementation boundary

Do not modify the existing prototype in place to retrofit the new strategy. Create a versioned, independently testable implementation, for example:
- `MSNR_PHASE6_EXPERIMENTAL`
- `MSNR_LAYER9_BODY_ATR14`
- `MSNR_LAYER9_BODY_ATR20`
- `MSNR_LAYER9_RANGE_ATR14`
- `MSNR_LAYER9_RANGE_ATR20`
- target variants `TARGET_RANGE_EDGE`, `TARGET_CONFIRMED_SWING`, `TARGET_OPPOSING_LIQUIDITY`

Use explicit configuration objects and immutable experiment IDs. Preserve the current detector as a legacy research prototype until migration and regression review are complete.

## 6. Proposed confirmation-window candidates (not selected or frozen)

To make “test separate confirmation windows” operational without tuning on outcomes, the following small candidate set is recommended for owner review:
- 1 completed candle
- 3 completed candles
- 5 completed candles

These are candidate experiment values only. The owner has not approved them. If approved, count candles from a precisely defined Phase 6 event timestamp; define whether the event candle is counted; expire the event at the end of the selected window; never extend a window after seeing market outcomes. Record all three variants, including failures.

## 7. Work still blocked

The compatibility audit does not resolve the mathematical blockers in the parent specification: sweep excursion and units, exact marker candle semantics, ATR estimator/timeframe, displacement threshold, structural-break definition, confirmation-window approval, pivot and liquidity-pool algorithms, stop buffer, time exit, entry/fill model, instrument/feed, and measured costs.

## 8. Governance disposition

This is a read-only source audit. No production code, strategy registry, capital plane, execution configuration, or live lock was changed.

- `LIVE_EXECUTION = BLOCKED`
- `capital_plane_mode = VERIFY_ONLY`
- `FINAL_EXECUTION_AUTHORIZATION = false`
- `research_capital_authority = false`

**Disposition:** Existing prototype is not equivalent to the new 3-6-9 specification. Keep both research-only and unqualified. Do not backtest the new model until its remaining rules and data/cost prerequisites are explicitly resolved.
