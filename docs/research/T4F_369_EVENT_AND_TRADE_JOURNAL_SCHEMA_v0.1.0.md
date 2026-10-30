# T4F × 369 Event and Trade Journal Schema v0.1.0

**Status:** Required research data contract. Not a frozen strategy.

## Recording model

Maintain two linked datasets:

1. **Candidate event ledger** — one row per structurally eligible T4F candidate, regardless of whether the 369 filter would admit it. This is the comparison denominator and must include candidates rejected by 369.
2. **Trade outcome ledger** — one row per simulated/filled trade outcome generated from the same frozen entry, stop, target, fill, and cost rules. Every outcome links to exactly one candidate ID.

Do not create a row only after a 369-qualified trade is selected. That would erase rejected candidates and create selection bias. For the structure-only comparator, preserve the same structural candidate cohort and evaluate the same hypothetical trade mechanics; the 369 variant adds only its pre-registered eligibility filter. Do not substitute ATR or Volume Profile as alternative frameworks; they are not part of the supplied T4F rules.

## Common identity and lineage fields

| Field | Type | Requirement |
|---|---|---|
| candidate_id | string | Required, immutable, unique candidate key |
| trade_id | string/null | Required for a trade outcome; null for candidate-only records |
| strategy_name | string | `T4F_X_369` |
| strategy_version | string | Frozen version identifier or explicit `UNFROZEN_RESEARCH` |
| instrument | string | Exact provider instrument code and display symbol |
| timeframe | string | E.g. M15 context and M1 execution; record both separately |
| timestamp_utc | ISO-8601 UTC | Event timestamp; include timezone-aware values |
| session_timezone | IANA timezone | E.g. `America/New_York`; never infer from machine timezone |
| session_date | date | Session date in the declared session timezone |
| dataset_id | string | Immutable dataset/run identifier |
| dataset_sha256 | 64-char hex | Hash of exact normalized dataset used |
| raw_source_sha256 | 64-char hex/null | Hash of original API response/file when available |
| source_provider | string | E.g. Deriv or approved broker/feed |
| source_symbol | string | Exact symbol resolved from provider discovery |
| granularity_seconds | integer | Exact bar duration |
| code_commit_sha | string | Repository commit used to produce result |

## T4F structure and opening reference fields

| Field | Type | Requirement |
|---|---|---|
| protected_swing_type | HIGH/LOW/null | Must remain null until protected-swing evidence is verified |
| protected_swing_price | decimal/null | Full exact reference price |
| swing_pivot_time_utc | timestamp/null | Pivot's occurrence time |
| swing_first_known_time_utc | timestamp/null | Earliest time the pivot could be known |
| structure_break_type | BOS/MSS/null | Do not infer from a mechanical pivot |
| structure_break_level | decimal/null | Exact opposing structural level broken |
| structure_break_time_utc | timestamp/null | Time of qualifying break |
| structure_break_evidence_id | string/null | Linked OHLC evidence or reviewer annotation |
| day_open_price | decimal/null | 00:00 opening reference; timezone rule must be frozen |
| london_open_price | decimal/null | 02:22 opening reference; timezone rule must be frozen |
| day_open_relation | ABOVE/BELOW/EQUAL/UNKNOWN | Directional reference only |
| london_open_relation | ABOVE/BELOW/EQUAL/UNKNOWN | Directional reference only |
| time_phase | string/null | Supplied 369/963 phase identifier |
| phase_timezone | IANA timezone/null | Required before phase is marked valid |

## 369 numerical fields

| Field | Type | Requirement |
|---|---|---|
| integer_part | integer | Floor of positive protected swing price |
| digit_sum | integer | Sum of integer-part decimal digits |
| digital_root | integer 1–9 | Repeated digit reduction |
| base_step | decimal | 12, 15 or 18 from supplied mapping |
| instrument_multiplier | decimal | XAUUSD=1; NQ=10; ES=1 supplied but unverified |
| scaled_step | decimal | base_step × multiplier |
| level_index | integer >= 1 | n in the projection formula |
| projected_level_price | decimal | Exact full-precision projected level |
| eligible_369 | boolean | Pre-registered pass/fail of the level condition |
| eligibility_rule_version | string | Frozen condition identifier |

## M15 interaction and M1 confirmation fields

| Field | Type | Requirement |
|---|---|---|
| m15_bar_open_time_utc | timestamp | Exact M15 candle start |
| m15_open/high/low/close | decimal | Preserve the actual OHLC observation |
| m15_interaction | enum | BODY_CROSS_ABOVE, BODY_CROSS_BELOW, WICK_REJECTION, NONE, UNKNOWN |
| m15_decisive_rule_version | string/null | Null until “decisive” is quantified |
| liquidity_side | BSL/SSL/null | BSL above recognizable highs; SSL below recognizable lows |
| liquidity_pool_price | decimal/null | Exact high/low defining pool |
| liquidity_sweep_time_utc | timestamp/null | Time of M1 sweep |
| m1_mss_bos_confirmed | boolean/null | Null when not assessed or definition unresolved |
| m1_structure_level | decimal/null | Level whose break confirms reversal/direction |
| m1_structure_time_utc | timestamp/null | Confirmation time |
| cisd_confirmed | boolean/null | Do not mark true without a frozen CISD rule |
| cisd_time_utc | timestamp/null | Confirmation time |
| cisd_displacement_value | decimal/null | Observed value; unit and threshold version required |

## FVG, fill, stop and exit fields

| Field | Type | Requirement |
|---|---|---|
| first_aligned_fvg_id | string/null | Identifier of the first qualifying FVG after confirmation |
| fvg_direction | BULLISH/BEARISH/null | Direction of the selected FVG |
| fvg_low | decimal/null | Exact FVG lower boundary |
| fvg_high | decimal/null | Exact FVG upper boundary |
| fvg_midpoint | decimal/null | (fvg_low + fvg_high) / 2 |
| fvg_formed_time_utc | timestamp/null | Time the gap became knowable |
| fvg_first_known_time_utc | timestamp/null | Must respect all bars required to identify FVG |
| entry_time_utc | timestamp/null | Actual or simulated fill time |
| entry_price | decimal/null | Fill price, not intended order price |
| entry_fill_model | string/null | Frozen market/limit/partial-fill rule |
| stop_price | decimal/null | Exact protective stop |
| stop_invalidation_reference | string/null | Exact rule/structure authorizing stop |
| stdv_38_2_target | decimal/null | Null until STDV anchor/calculation is defined |
| stdv_61_8_target | decimal/null | Null until STDV anchor/calculation is defined |
| stdv_100_target | decimal/null | Null until STDV anchor/calculation is defined |
| stdv_161_8_target | decimal/null | Null until STDV anchor/calculation is defined |
| exit_time_utc | timestamp/null | Outcome time |
| exit_price | decimal/null | Actual or simulated exit fill |
| exit_reason | enum/null | TARGET, STOP, TIME, MANUAL, DATA_INVALIDATION, OPEN |
| max_favorable_excursion_r | decimal/null | Computed from actual post-entry path |
| max_adverse_excursion_r | decimal/null | Computed from actual post-entry path |

## Costs, sizing and outcome fields

| Field | Type | Requirement |
|---|---|---|
| account_currency | string | Currency of account/PnL calculation |
| contract_multiplier | decimal/null | Provider contract specification; required for monetary PnL |
| position_size | decimal/null | Hypothetical or actual size |
| risk_usd | decimal/null | Initial stop risk in USD; no invented affordability |
| gross_pnl_usd | decimal/null | Before separately recorded costs |
| commission_usd | decimal | Non-negative, separately recorded |
| spread_cost_usd | decimal | Non-negative, separately recorded |
| slippage_cost_usd | decimal | Non-negative, separately recorded |
| financing_cost_usd | decimal | Non-negative where applicable; otherwise explicit zero with reason |
| net_pnl_usd | decimal/null | Gross PnL less all recorded costs |
| net_r_multiple | decimal/null | net_pnl_usd / risk_usd when valid |
| outcome_status | enum | WIN, LOSS, BREAKEVEN, OPEN, INVALID, NOT_TRADED |
| exclusion_code | string/null | Machine-readable exclusion reason |

## Hard validation rules

- A mechanical pivot is not a Protected Swing. Require a structure-break evidence ID and an exact protected-swing annotation before setting protected_swing_type HIGH/LOW.
- A candidate row must exist even when eligible_369 is false.
- Do not use future bars before their close/availability timestamp. A pivot and FVG each require a first-known timestamp.
- `eligible_369` must be a real boolean, never a string/number.
- Recompute digital root and projected level from the recorded reference and instrument mapping; reject mismatches.
- Do not set an M15 decisive breakout until its decision threshold/version is frozen.
- Do not set CISD confirmed or FVG valid from a visual claim without the linked OHLC evidence and deterministic definition.
- Do not compute an STDV target until its anchor, sample, estimator and projection basis are versioned.
- Costs must be non-negative. Net PnL must reconcile to gross PnL minus all recorded costs.
- Every outcome must be linked to a candidate ID, data hash, strategy version and code commit.
- Missing/unresolved required evidence is NULL / UNKNOWN and fails strategy evaluation; never forward-fill missing setup data.

## Interpretation

This schema is deliberately more detailed than the sample PnL table. It preserves enough mechanical context to audit each decision and to reproduce an ablation test. Recording a field does not mean the rule that generates it has been defined or validated.
