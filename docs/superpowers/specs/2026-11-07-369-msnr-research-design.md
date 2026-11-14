# AURELIA 369/MSNR Research Design v0.1

**Status:** Approved design; implementation not yet started  
**Date:** 2026-11-07  
**Canonical base:** `main` at `d04564aca0648201feff0326fe9af0fbcee92e94`  
**Working branch:** `research/369-msnr-design-20261107`

## Intent

Add a separately versioned, research-only 369/MSNR strategy variant to AURELIA. The objective is to test whether protected-swing 369 levels, MSNR liquidity-sweep confirmation, a New York signal-close window, a minimum 3R geometric target distance, and optional displacement/extension filters produce positive, robust net expectancy after realistic costs.

The strategy is not qualified and must not be connected to capital authorization or order submission.

## Approved behavior

### Timing

- Use `zoneinfo.ZoneInfo("America/New_York")`; do not hard-code EST as UTC-5.
- Evaluate eligibility on the **confirmed signal candle close timestamp**, not its open timestamp.
- The eligible interval is half-open: **[09:45:00, 10:00:00)** New York local time.
- A close at 09:45:00 is eligible; a close at 10:00:00 is not.
- Enter at the next available bar's open, consistent with `StrategyCandidate.entry_timing="NEXT_BAR_OPEN_AFTER_SIGNAL"`.
- Never fill at the signal candle close.
- Reject naive timestamps, missing next bars, duplicate/out-of-order bars, malformed OHLC, and stale/incomplete inputs.
- Report results independently by timeframe. An M15 signal close at 09:45 is generally the only standard M15 close in this window; M1 can generate multiple close events.

### 369 level hypothesis

Use the protected swing's actual price as the anchor. Apply the digital-root mapping to the integer portion only:

| Digital root | Level step |
|---|---:|
| 1, 4, 7 | 12 |
| 2, 5, 8 | 15 |
| 3, 6, 9 | 18 |

Generate bearish levels downward from a protected high and bullish levels upward from a protected low, with at least four levels in each applicable direction. Preserve the anchor's fractional component in each level.

Examples supplied in the approved discussion: 4217.395 maps to digital root 5 and step 15, yielding 4202.395, 4187.395, 4172.395, and 4157.395.

Instrument scaling/precision must be explicit and source-verified before enabling a symbol. Proposed mappings mentioned in discussion (NQ x10; XAUUSD as-is; ES as-is) are unverified configuration candidates, not production facts. Unknown mapping, unsupported digital root, invalid tick precision, or unavailable protected swing must fail closed. The exact anchor convention and mapping must be independently checked against the user's authoritative 369 source material before qualification.

### Signal construction

- Reuse the existing deterministic MSNR liquidity-sweep detector and its validated bar/time contracts where compatible.
- Do not duplicate or fork the canonical capital engine, risk authority, or execution firewall.
- A candidate requires a completed liquidity sweep, reclaim/close confirmation, and the registered structural confirmation.
- The displacement variant requires the confirming candle body to exceed 1.5 times the mean body of the preceding three completed candles. No current/future candle may enter this calculation.
- The protected swing must be established without look-ahead. Its confirmation time must be recorded separately from its pivot timestamp.
- Calculate the initial stop from the sweep extreme plus a declared buffer. The buffer must be expressed in instrument ticks or another explicitly configured unit.
- Select the relevant opposing 369 level as the target. The target-selection rule must be deterministic and recorded with every candidate.

### 3R eligibility

Compute geometric reward/risk from the **actual simulated next-bar-open entry**, target level, and initial stop. Reject candidates below 3.0 gross R. This is a target-distance eligibility condition, not a guarantee of realized 3R or positive net return.

This is a new versioned variant. Do not combine it with the earlier 2R variant or overwrite existing MSNR behavior.

### Optional filters and ablations

Register distinct variants rather than silently enabling filters:

1. Baseline: 369 + MSNR + close-time gate + 3R.
2. Displacement: baseline plus body > 1.5 x prior-three-body mean.
3. EMA/ATR extension: baseline plus `abs(price - EMA20) > 2 x ATR14` rejection.
4. Ablation: baseline without displacement.

Treat the EMA20/ATR14 extension condition as an unproven hypothesis. Measure whether it improves net expectancy and drawdown; do not assume it removes unhealthy moves. Compute EMA/ATR only from completed bars with explicit warm-up and missing-data rules.

### 08:49:55 marker

The 08:49:55 New York marker is not part of the 369 arithmetic and is not an execution trigger in this version. Its precise calculation, input series, event timestamp semantics, and required data granularity are not fully specified in the approved material. Keep it out of the initial implementation; add it only as a separately registered feature after its source definition is supplied and reviewed. M1 OHLC cannot reconstruct an exact second-level event reliably.

## Simulator and data requirements

- Use a deterministic event-driven research simulator; no broker calls or capital authority.
- Model next-bar-open fills, gaps through stops/targets, spread, slippage, commission, other fees, and latency where supported by source evidence.
- Spread and slippage must be separate cost components; slippage estimates must not double-count spread.
- Unknown or stale cost profiles block qualification; never substitute invented costs or zero-cost assumptions.
- If TP and SL are both touched in one OHLC bar and sequencing is unknowable, use the conservative stop-first outcome or higher-resolution data.
- Record signal time, fill time/price, stop, target, gross R, all costs, net P&L/R, exit reason, data provenance, strategy version, configuration hash, and dataset hash.
- No end-of-dataset exit may be mislabeled as an end-of-day exit. Any forced liquidation policy must be explicit and timezone-aware.
- Validate data continuity, duplicates, gaps, OHLC invariants, symbol identity, timeframe, timezone, and source freshness before simulation.

## Goals

- A deterministic, auditable, reproducible research candidate.
- No look-ahead or same-bar fill bias.
- Instrument-specific, cost-adjusted performance measurement.
- Registered baseline, filter, and ablation comparisons.
- Walk-forward and sealed prospective out-of-sample validation.
- Evidence sufficient to decide whether the strategy merits further research, not an automatic live release.

## Non-goals and anti-goals

- No live trading, demo order placement, broker authentication, stake sizing, or order routing.
- No modification of `config/LIVE_LOCK.yaml`, `FINAL_EXECUTION_AUTHORIZATION`, capital plane, risk authority, or execution firewall.
- No claiming that a 3R target distance guarantees a 3R realized return.
- No tuning on sealed OOS data, repeated unregistered parameter search, or reporting only favorable symbols/regimes.
- No inferred 08:49:55 event from M1 OHLC.
- No claiming profitability or qualification before verified data, costs, full validation, and evidence review.

## Qualification and verification

- Unit tests must be written first and observed failing for each new behavior, then pass after minimal implementation.
- Cover 09:45 inclusion, 10:00 exclusion, DST spring/fall transitions, UTC/local conversions, naive timestamps, missing next bars, and M1/M15 close semantics.
- Test 369 digital-root mapping, integer-only root input, fractional anchor preservation, level direction/count, instrument scaling, tick precision, and invalid/unknown mappings.
- Test protected-swing confirmation and MSNR sequencing with no future-bar access.
- Test next-bar-open fills, gap-through-stop/target, both TP/SL touched in one bar, costs, and end-of-data behavior.
- Compare baseline and registered variants using net expectancy, profit factor, max drawdown, R distribution, trade count, cost sensitivity, and regime/timeframe segmentation.
- Follow AURELIA's existing walk-forward governance. The current policy's 100-trade minimum applies per strategy x symbol x regime cell where required, not as an aggregate substitute. Use a sealed prospective OOS protocol and multiple-testing/repeated-trial adjustment.
- A successful unit test or backtest does not qualify the strategy or authorize live execution.

## Architecture touchpoints

- Reuse `research/labs/deterministic_intraday_strategies.py` and its `StrategyBar` / `StrategyCandidate` contracts where appropriate.
- Reuse `research/labs/intraday_bias_cost_model.py` for verified instrument cost and latency profiles.
- Reuse `runtime/validation/walk_forward.py` and `docs/AURELIA_RESEARCH_GOVERNANCE.yaml` for OOS qualification.
- Add a distinct research module, tests, and registry entry only after the implementation plan is reviewed.
- Keep all changes under research/validation/docs; do not modify capital or execution paths.

## Approaches considered

1. **Modify the existing MSNR detector in place:** smallest apparent diff, but changes existing strategy semantics and makes historical comparisons ambiguous. Rejected.
2. **Create a separate versioned research candidate reusing the existing detector and bar contracts:** preserves current behavior, enables clean baseline/ablation comparison, and confines changes to research. **Selected and approved.**
3. **Build a separate strategy/execution engine:** duplicates existing contracts and creates avoidable drift. Rejected.

## Remaining implementation decisions

The builder may choose internal helper names and data structures consistent with repository conventions. Before qualification, obtain authoritative confirmation of the protected-swing anchor convention and each instrument's scale/tick precision; these are data/configuration gates, not assumptions to fill silently.

## Security invariants

The canonical `config/LIVE_LOCK.yaml` remains unchanged:

```yaml
live_trading_enabled: false
FINAL_EXECUTION_AUTHORIZATION: false
LIVE_EXECUTION: BLOCKED
capital_plane_mode: VERIFY_ONLY
research_capital_authority: false
external_repositories_capital_forbidden: true
blind_resubmission: false
kill_switch_independent: true
```

Only the existing AURELIA capital plane can authorize capital actions. Research agents, ChatGPT, external plugins, and this strategy cannot change that boundary.
