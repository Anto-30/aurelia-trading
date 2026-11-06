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
