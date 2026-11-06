# Strategy Campaign Seal — Negative OOS Result

**Seal date:** 2026-11-06  
**Seal state:** `SEALED_SUMMARY_ONLY_WITH_PROVENANCE_GAPS`  
**Qualification disposition:** `DOES_NOT_QUALIFY`  
**Execution disposition:** `LIVE_EXECUTION=BLOCKED`

## Campaign identification

| Field | Recorded value |
|---|---|
| Campaign ID / UUID | Not supplied in the source result |
| Strategy name / version | Not supplied in the source result |
| Symbol | Not supplied; not inferred |
| Timeframe | Not supplied; not inferred |
| Campaign start / end | Not supplied |
| Sealed by | Operator-directed governance record; individual sign-off identity not included in the source result |
| Source | Metric table supplied by the system owner on 2026-11-06 |
| Raw dataset / manifest | Not attached to the supplied result |
| Raw evidence SHA-256 | Not available; no source artifact was supplied |

This seal preserves the supplied outcome without inventing campaign identifiers, sample counts, symbol, timeframe, dates, data lineage, or a raw-evidence hash. It is an immutable summary record, not a claim that the underlying observations have been independently reproduced.

## Results summary

### Out-of-sample performance

| Metric | Observed result | Qualification threshold | Status |
|---|---:|---:|---|
| OOS directional win rate | 50.73% | >51.28% (reported break-even threshold) | **FAIL** |
| Mean quoted net return | −1.07% per stake | >0% | **FAIL** |
| Qualifying calibration buckets | 2 of 3 | 3 of 3 | **FAIL** |
| Maximum reliability gap | 17.33% | <10% | **FAIL** |

### Interpretation

1. The observed directional win rate is 0.55 percentage points below the stated 51.28% break-even threshold; it also fails the strict requirement to exceed that threshold.
2. Mean quoted net return is negative at −1.07% per stake. On the supplied quoted economics, the strategy has negative expected value.
3. Only two of the three required calibration buckets qualify.
4. The 17.33% maximum reliability gap exceeds the stated 10% ceiling by 7.33 percentage points.

All four reported qualification tests fail. The campaign is therefore **disqualified and must not be promoted**. The negative quoted net return is an economic disqualification, not a justification to retune the same frozen campaign until it passes.

## Sealing and anti-retuning controls

- Preserve the reported metrics exactly as supplied.
- Do not overwrite, relabel, omit, or reinterpret these negative results.
- Do not change the break-even threshold, execution-cost assumptions, calibration criteria, or evaluation window for this sealed campaign.
- Do not reuse this campaign's OOS observations for iterative parameter tuning.
- Do not promote this campaign to live execution, automated execution, or strategy eligibility.
- Any materially new hypothesis must receive a new campaign ID, a pre-registered evaluation protocol, fresh or properly isolated OOS data, source-bound execution-cost evidence, and independent review.
- If the original raw data, manifest, trade-level outputs, cost quotes, sample size, or code commit are later provided, append a provenance addendum referencing their immutable hashes. Do not silently amend this summary or replace its recorded outcomes.

## Evidence limitations

The supplied metric table does not include the campaign UUID, strategy version, symbol, timeframe, start/end timestamps, OOS trade count, trade-level outcomes, quoted contract records, calibration-bucket definitions, confidence intervals, source dataset hash, code commit, or calculation report. These omissions prevent independent numerical reproduction and statistical-uncertainty analysis.

Accordingly:
- The reported figures are recorded as operator-supplied results.
- The arithmetic comparisons against the supplied thresholds are straightforward and recorded above.
- This seal does not claim independent backtest execution, data integrity verification, or reproduction of the underlying calculation.
- The absence of provenance does not convert a failed result into a pass; it limits what can be certified about how the figures were produced.

## Governance

```yaml
strategy_qualification: DOES_NOT_QUALIFY
strategy_campaign_status: SEALED_SUMMARY_ONLY_WITH_PROVENANCE_GAPS
live_trading_enabled: false
LIVE_EXECUTION: BLOCKED
FINAL_EXECUTION_AUTHORIZATION: false
capital_plane_mode: VERIFY_ONLY
research_capital_authority: false
```

**Final disposition:** retain this campaign as a negative research result. Do not retune it for qualification and do not use it to authorize capital.


## Provenance addendum — recovered Actions artifact (2026-11-07)

The source summary's provenance gaps have been narrowed using the existing research artifact; the original negative metrics and seal disposition above are preserved unchanged.

### Recovered artifact identity

- GitHub Actions run: `41420980026` (scheduled R_100 prospective collection run #342).
- Artifact ID: `13130052450`.
- Artifact file: `r100-prospective-oos-run-342.zip`.
- ZIP SHA-256: `a433bbc8a257e4abc22ef1713cbb1cf1b533541d3624528eedbd4ac90be242ed`.
- Embedded state: `aurelia_r100_state.json`, 548,286 bytes.
- Embedded state SHA-256: `e120937647ccf31a954a7ba38bb1366845468714f1d4750c9ceab3eefeb31058` (matches the archive hash recorded in PR #253).
- Experiment: `R100-PROSPECTIVE-20261008T192038Z`.
- Hypothesis: `H-R100-TICK-MOMENTUM-001`.
- Strategy: `R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0`, version `0.2.0`.
- Instrument: all 783 observation rows identify `R_100`; each uses a 10-tick horizon. The manifest is tick-stream research, not M1/M15 candle evidence.
- Frozen source commit: `67922e738acd06e9f77d434819df1a56aa11974d`.
- Config hash: `cca748c28c1253bf047743c46a208e114c6ade2601fb5aa5bbedcc2dcfa2ad15`.
- Manifest: one predeclared trial, zero search degrees of freedom, zero OOS reuse; parameters were window 64, minimum observations 20, threshold 1.5, cooldown 30 seconds, horizon 10 ticks.

### Source-state completeness

- Campaign start: `2026-10-08T19:20:38.482344Z`.
- OOS start: `2026-10-09T19:20:38.482344Z`.
- Planned campaign end: `2026-10-15T19:20:38.482344Z`.
- Last collector completion: `2026-10-15T16:28:53.295927Z`, approximately 2h 51m 45s before the planned end.
- Settled observations: 783 total (170 pre-OOS, 613 OOS).
- Proposal quote observations: 784.
- Pending observations: 1.
- The recovered source manifest has `sealed=false`. This artifact is a terminal collection snapshot, not an already sealed campaign. The pending signal must remain `UNRESOLVED_NO_BACKFILL`; do not extend or backfill the campaign.

### Independent recalculation from the recovered OOS observations

| Metric | Recalculated value |
|---|---:|
| OOS wins / observations | 311 / 613 |
| OOS hit rate | 50.7341% |
| Mean predicted probability | 64.7157% |
| Brier score | 0.270921 |
| Constant-base-rate Brier | 0.249946 |
| Mean direction-adjusted underlying return | +0.01265% per observation |
| Quoted payout / stake | 1.95 |
| Quoted break-even probability | 51.2821% |
| Mean quoted net return / stake | -1.0685% |

The positive direction-adjusted underlying return is not realized contract profit and does not override the negative quoted contract expectancy.

A naive independent-Bernoulli 95% Wilson interval for the hit rate is approximately 46.78%–54.67%; it includes the quoted break-even rate. A naive iid normal interval for mean quoted net return is approximately -8.79% to +6.66%. These intervals are descriptive only: serial dependence and overlapping signal horizons were not adjusted, so they are not qualification-grade uncertainty estimates.

### Calibration policy reconciliation

The recovered campaign manifest and frozen collector specify:
- minimum 3 qualifying buckets;
- minimum 10 observations per bucket;
- maximum reliability gap 5%.

Recomputed buckets:
- 0.60–0.65: 396 observations; mean probability 63.5914%; realized rate 51.7677%; gap 11.8237 percentage points.
- 0.65–0.70: 209 observations; mean probability 66.6161%; realized rate 49.2823%; gap 17.3338 percentage points.
- 0.70–0.75: 8 observations; below the 10-observation minimum, so not qualifying; observed gap 33.2224 percentage points.

Only 2 of 3 buckets qualify. The 17.3338-point maximum gap among qualifying buckets exceeds the campaign's configured 5% ceiling by 12.3338 points. The original summary's 10% threshold is retained as originally supplied; the recovered manifest/code establish that the actual campaign policy was stricter at 5%.

### Disposition

The recovered artifact independently reproduces the negative headline metrics from the saved observations and narrows the lineage gaps. It does not provide the original full tick tape, an independently verified Deriv source export, a completed campaign seal, or dependence-adjusted confidence intervals. Keep the strategy retired from qualification. Preserve the one pending observation as unresolved, run only the offline snapshot-preserving sealer after its source code is reviewed, and do not retune this campaign or reuse its OOS observations.
