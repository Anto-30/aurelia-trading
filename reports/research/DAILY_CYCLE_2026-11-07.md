# AURELIA Daily Research & Training Cycle — 2026-11-07

**Research cut-off:** 2026-11-07 00:48 EAT  
**Market data cut-off:** US cash close 2026-11-06  
**Repository:** `Anto-30/aurelia-trading`, main  
**Mode:** research and assurance only; no capital authority

## Executive disposition

| Control | Result |
|---|---|
| Daily research review | COMPLETE |
| New strategy/model training | NOT RUN |
| Fresh R_100 public transport evidence | Latest verified PR #279 probe passed; not rerun in this cycle |
| R_100 historical M1/M15 dataset | BLOCKED |
| Contract execution economics | UNVERIFIED |
| Existing R_100 v0.2.0 | RETIRED FROM QUALIFICATION |
| Account evidence | BLOCKED: no documented read-only account scope |
| Main-branch scheduled credential containment | NOT APPLIED; workflow state not verified in UI |
| LIVE_EXECUTION | BLOCKED |
| FINAL_EXECUTION_AUTHORIZATION | false |

No strategy hypothesis is promoted by this report. Market context is not evidence of a predictive relationship with Deriv synthetic indices.

## 1. Market intelligence

### US session — Friday, November 6

The connected Alpaca IEX daily-bar feed returned two bars per symbol for November 5 and 6. The following close-to-close changes are calculated from those IEX bars:

| Instrument | Nov 5 close | Nov 6 close | Change |
|---|---:|---:|---:|
| SPY | 733.43 | 735.40 | +0.269% |
| QQQ | 648.05 | 656.31 | +1.275% |
| DIA | 514.56 | 512.21 | -0.457% |
| TLT | 81.915 | 81.920 | +0.006% |
| GLD | 375.55 | 372.55 | -0.799% |
| USO | 148.18 | 148.43 | +0.169% |

These are IEX ETF observations, not consolidated SIP index returns, futures prices, spot commodity prices, or Deriv synthetic-index data. IEX volume and trade counts must not be treated as consolidated market volume.

AP's November 6 close summary reports S&P 500 +0.3%, Nasdaq Composite +1.1%, Russell 2000 +0.9%, and Dow -0.5%. The rebound did not erase the week's losses: Nasdaq -3.4%, S&P 500 -2.7%, Russell 2000 -2.1%, and Dow -0.9%. The prior session's technology-led selloff was followed by a partial rebound, not a confirmed regime reversal.

Reuters reported South Korea's KOSPI down 6.02% on November 6, with an intraday trading halt after a sharper fall. Semiconductor weakness and concerns about possible changes to AI/data-centre investment policy remained a global risk factor.

**Regime assessment:** MIXED / EVENT-DRIVEN REBOUND AFTER TECHNOLOGY-LED SELLOFF. This is broad-market context only. AURELIA's R_100 regime remains UNCLASSIFIED.

Sources:
- AP, US market close, November 6, 2026: https://apnews.com/article/806f71d95105bc7efbc760b194dd8cad
- Reuters, South Korea market selloff, November 6, 2026: https://www.reuters.com/world/asia-pacific/south-korea-stocks-plunge-8-circuit-breaker-triggered-chip-shares-tumble-2026-11-06/

## 2. Global macro and catalysts

The US Bureau of Labor Statistics released the October 2026 Employment Situation on November 6 at 08:30 ET:

- Nonfarm payrolls: +165,000.
- Unemployment rate: 4.1%.
- Average hourly earnings: +0.4% month over month and +3.1% year over year.
- Average workweek: 34.4 hours, unchanged.
- August and September payroll estimates revised upward by a combined 84,000.
- Employment gains were concentrated in professional/business services, health care, transportation/warehousing, and manufacturing.

The report is stronger than the prior month's initial estimate, but one release does not establish a durable labor-market regime or a synthetic-index trading edge.

Upcoming BLS releases:
- October CPI and Real Earnings: November 10, 2026, 08:30 ET (16:30 EAT).
- October PPI: November 13, 2026, 08:30 ET (16:30 EAT).

US session code must use the IANA zone `America/New_York`, not a fixed UTC offset. The November 1 daylight-saving transition has already occurred.

Sources:
- BLS, October 2026 Employment Situation: https://www.bls.gov/news.release/archives/empsit_11062026.htm
- BLS, November 2026 selected release calendar: https://www.bls.gov/schedule/2026/11_sched.htm

## 3. Deriv public research and account boundary

### PR #279 — consolidated public-only research candidate

Branch: `security/deriv-readonly-r100-integrated-20261106`  
Head: `f4502a0598b98b0c8e931fd2756fbf2c73cfe293`

Exact-head run evidence:
- AURELIA Assurance run 42220072100: success.
- Agent Federation Audit run 42220072121: success.
- Agent Continuity Watchdog run 42220072925: success.
- Claude Code read-only reviewer run 42220072282: skipped as expected because the PR was draft.

Assurance reported 84 research-plane tests, 12 auth-gate tests plus 6 prerequisite tests, 61 assurance tests, 351 runtime tests, and 12 hardening tests passing. The public R_100 probe verified active-symbol discovery, valid M1 candles, and two ordered live ticks without account credentials or an Authorization header.

This is a public transport smoke test. It is not a two-year historical dataset, completed prospective campaign, authenticated account lifecycle, or strategy qualification. The PR itself records readiness DEGRADED / CAPITAL_PROTECTED, readiness false, continuous runtime unavailable, account evidence blocked, and live release gate blocked.

### Main-branch scheduled credential risk

Direct reads of main show:
- `.github/workflows/aurelia-free-runtime.yml` still has a 15-minute schedule and authenticated jobs mapping `DERIV_AUTH_TOKEN || DERIV_PAT` and account metadata.
- `.github/workflows/deriv-auth-evidence.yml` still has a six-hour schedule and maps Deriv account credentials.
- `.github/workflows/aurelia-assurance.yml` still combines pull-request CI with the production environment and Deriv secret references.

The scheduled definitions are present on main. The Actions UI enabled/disabled state was not verified: the browser session was unauthenticated, and no workflow was changed. Do not treat a failed UI inspection as evidence that workflows are disabled.

### PR #280 — scheduled credential removal

Branch: `security/legacy-auth-scheduled-remediation-20261106`  
Head: `c8c71dac90916ad17748de0d444de262dae50a9e`

Exact-head Assurance, Federation Audit, Continuity Watchdog, and Legacy Authentication Static Audit passed. The static audit reported 17 workflow files, zero scheduled Deriv credential workflows, zero pull-request Deriv credential workflows, and four manual Deriv-auth workflows.

This is branch evidence only; main remains unchanged. PR #280 and PR #283 overlap in workflow files and must not be merged independently without one integration plan.

### PR #283 — universal Deriv scope block

Branch: `security/deriv-scope-and-workflow-audit-20261106`  
Head: `e49cd4315ad95eaa1618d03506bde8ecf744c807`

Exact-head Assurance and Deriv Credential Boundary Audit passed. The audit scanned 17 workflow files and 11 credential-boundary tests passed. The patch:
- blocks account authentication before reading account credential values;
- makes the public research client reject account-credential key presence, including empty values;
- removes Deriv secret mappings from the secret-presence report;
- adds a workflow-wide audit for direct Deriv secret references and credential environment bindings.

The audit is static and pattern-based; it is not a proof against every indirect/transitive secret flow. Independent security review remains required. Claude review was skipped on the draft PR.

### PR #282 — safe diagnostics

Head: `b92e0dac7491ee0d6200297f7277654c4c34dc1d`. Exact-head Assurance passed. It adds bounded repository-relative failure frame metadata while excluding exception messages, source lines, locals and request/response payloads. This is diagnostic instrumentation, not a root-cause fix for the authenticated lifecycle `ValueError`.

## 4. Recovered R_100 campaign artifact and independent recalculation

Artifact ID `13130052450`, from Actions run `41420980026` (#342), was downloaded and inspected.

- ZIP SHA-256: `a433bbc8a257e4abc22ef1713cbb1cf1b533541d3624528eedbd4ac90be242ed`.
- Embedded `aurelia_r100_state.json`: 548,286 bytes.
- Embedded state SHA-256: `e120937647ccf31a954a7ba38bb1366845468714f1d4750c9ceab3eefeb31058`.
- Experiment: `R100-PROSPECTIVE-20261008T192038Z`.
- Hypothesis: `H-R100-TICK-MOMENTUM-001`.
- Strategy: `R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0`.
- Frozen code commit: `67922e738acd06e9f77d434819df1a56aa11974d`.
- Config hash: `cca748c28c1253bf047743c46a208e114c6ade2601fb5aa5bbedcc2dcfa2ad15`.
- One predeclared trial, zero search degrees of freedom, zero OOS reuse.
- 783 observations, all identifying R_100 with a 10-tick horizon; 784 proposal quotes; one pending signal.
- 170 pre-OOS observations and 613 OOS observations.
- Campaign planned end: 2026-10-15T19:20:38Z; last collection completed 2026-10-15T16:28:53Z, approximately 2h51m45s before planned end.
- The recovered manifest says `sealed=false`. The pending signal remains unresolved; do not backfill it.

Independent recalculation from the recovered OOS observations:

| Metric | Result |
|---|---:|
| OOS wins / observations | 311 / 613 |
| Hit rate | 50.7341% |
| Mean predicted probability | 64.7157% |
| Brier score | 0.270921 |
| Constant-base-rate Brier | 0.249946 |
| Direction-adjusted underlying return | +0.01265% per observation |
| Quoted payout / stake | 1.95 |
| Quoted break-even probability | 51.2821% |
| Mean quoted net return / stake | -1.0685% |

The positive direction-adjusted underlying return is not realized contract profit. The Brier score is worse than the constant-base-rate benchmark. A naive iid 95% Wilson interval for the hit rate is approximately 46.78%–54.67%; a naive iid normal interval for quoted net return is approximately -8.79% to +6.66%. Both include their respective break-even/zero thresholds. Serial dependence and overlapping signal horizons were not adjusted, so these are descriptive, not qualification-grade uncertainty intervals.

The campaign manifest and collector policy require at least three calibration buckets, at least ten observations per bucket, and a maximum reliability gap of 5%. Recalculated buckets:
- 0.60–0.65: n=396; mean probability 63.5914%; realized rate 51.7677%; gap 11.8237pp.
- 0.65–0.70: n=209; mean probability 66.6161%; realized rate 49.2823%; gap 17.3338pp.
- 0.70–0.75: n=8, below the ten-observation minimum; non-qualifying.

Only two buckets qualify; the maximum qualifying gap is 17.3338pp, exceeding the configured 5% ceiling. PR #285's original summary used a 10% threshold; its provenance addendum now records the stricter 5% campaign policy without rewriting the original supplied summary.

**Disposition:** v0.2.0 remains RETIRED_FROM_QUALIFICATION. Do not tune on this OOS sample. The raw state artifact contains observations and proposal quotes, not the complete original tick tape or an independent Deriv source export.

## 5. Strategy registry and integration repairs

### PR #286 — strategy identity without eligibility

Branch: `research/register-r100-prospective-strategy-20261106`  
Latest fix commit: `0d20556106f169593400a7d72a0465046c453586`

The PR registers `R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0` as `RESEARCH_ONLY_UNQUALIFIED`, with no verified instrument ID, strategy hash, reviewer, qualification evidence, costs, WFA/OOS or calibration qualification.

The initial Assurance run failed because a test expected `ACCOUNT_DERIV_AUTH_MODE: "oauth"` while the new credential-free workflow correctly uses `"none"`. I corrected that assertion on the PR branch only. The fix commit's Assurance run 42300119953 and credential-boundary audit run 42300119750 both passed; Claude review was skipped. The PR remains draft and is stacked on PR #283.

### Main-branch policy/data gaps

Direct main reads still show:
- `config/runtime.yaml`: minimum probability 0.50, maximum 0.75.
- Collector branch policy: minimum 0.55, maximum 0.75.
- `config/costs.yaml`: NOT_FOUND.
- `data/raw/r100_1m.csv`: NOT_FOUND.
- `data/frozen/r100_dual_resolution_manifest.json`: NOT_FOUND.

A single canonical probability policy is required. Do not treat PR #263 or collector constants as deployed until integrated and reviewed.

## 6. Research-domain disposition

| Domain | Disposition |
|---|---|
| Market structure / BOS / MSS / protected swings | Deterministic research logic exists; no new empirical R_100 validation |
| Liquidity sweeps / reclaim | Candle-derived proxy only; no resting-liquidity evidence |
| Fair-value gaps | Candidate logic exists; no cost-adjusted expectancy |
| Opening-range / consolidation breaks | No synchronized, validated R_100 M1/M15 sample |
| Trend / momentum | No new experiment; v0.2.0 remains retired |
| Mean reversion | No controlled R_100 comparison |
| Volatility | No new R_100 regime model |
| Tick dynamics | Old prospective artifact only; no new live sample in this cycle |
| Multi-timeframe | M15 sweep -> closed M1 MSS -> first aligned FVG midpoint retest remains a pre-registered hypothesis, not an edge claim |
| Microstructure | No true DOM, CVD/delta, aggressor-side tape or order-book evidence |
| ML / feature engineering | No training; deterministic baseline first |
| Calibration / uncertainty | Recalculation adverse; dependence-aware intervals not available |
| Position sizing / drawdown / tail risk | No new simulation; contract economics missing |
| Execution costs | No canonical costs file or observed fills |
| Walk-forward / OOS | No new valid run |
| Monte Carlo | Not run; no qualified net-return distribution |
| Ablation | Structure-only vs structure+369 remains the first paired experiment |
| Parameter sensitivity | Not run |
| Multiple testing | Register every new variant before OOS; no reuse of sealed OOS |
| Strategy retirement / revalidation | v0.2.0 remains retired; new version requires new campaign and fresh isolated OOS |
| Engineering / risk | Main scheduled credential injection, subprocess environment inheritance, history and cost gaps remain |

## 7. Ranked hypotheses and agent assignments

Assignments below are routing recommendations. No external agent execution is claimed.

| Priority | Workstream | Primary owner | Independent challenge |
|---|---|---|---|
| P0 | Remove scheduled Deriv credential injection from main and integrate one reviewed security branch | ClaudeCode / repository owner | GoogleAgentSkills, JEV, GLM |
| P0 | Remove inherited parent environment from advisory subprocesses; enforce explicit allowlist and authenticated worker protocol | ClaudeCode | GoogleAgentSkills, GLM |
| P0 | Integrate PR #279 public-only transport and credential boundary without enabling account auth | ClaudeCode | JEV, GLM |
| P1 | Acquire and freeze date-scoped R_100 M1/M15 history with continuity, OHLC, duplicate and SHA checks | ClaudeCode | JEV |
| P1 | Reconcile probability floor 0.50 vs 0.55 and source-backed contract economics | ClaudeCode | JEV, GLM |
| P2 | M15 protected-level sweep -> M1 MSS -> first aligned FVG retest versus structure-only baseline | KimiK3 | JEV, GLM |
| P3 | Structure-only versus structure+369 paired ablation | KimiK3 | JEV, GLM |
| P4 | MSNR Phase 6/9 with frozen BODY/FULL_RANGE definitions and pre-registered parameters | KimiK3 | JEV, GLM |
| P5 | Opening-range/consolidation breaks versus trend and mean-reversion baselines | KimiK3 | JEV |
| P6 | ML only after deterministic baseline, leakage tests, feature stability and calibration gates | KimiK3 | JEV, GLM |

GrokBot remains market-context/orchestration only. Layer 6 remains deterministic risk veto; no agent or LLM receives capital authority. The Claude read-only GitHub reviewer was skipped on the inspected draft PRs. DeepSeek Harness and Hermes execution were not verified.

## 8. Smallest safe repair sequence

1. Repository owner disables the two credential-bearing scheduled workflows in GitHub Actions until the reviewed replacement is merged. This run could not verify the UI state because the browser session was unauthenticated; no workflow setting was changed.
2. Review and integrate PR #280's scheduled-credential removal with PR #279/#283's public-only account boundary. Resolve overlapping workflow changes in one branch; do not merge parallel versions independently.
3. Review PR #254's subprocess isolation; main's `runtime/agent_workers.py` still launches configured commands without an explicit sanitized environment mapping.
4. Complete the offline snapshot-preserving campaign sealer for the recovered expired R_100 state, leaving the one pending signal unresolved and preserving the historical metrics unchanged.
5. Acquire valid date-scoped R_100 M1/M15 history and freeze the manifest.
6. Establish verified payout, stake, point-value, spread, commission, fill and slippage inputs; restore `config/costs.yaml`.
7. Reconcile the probability floor into one canonical source.
8. Run the frozen structure-only baseline before 369 ablation, calibration, WFA/OOS, dependence-aware Monte Carlo, parameter sensitivity and multiple-testing correction.

## 9. Governance verification

Main `config/LIVE_LOCK.yaml` was read directly. Blob SHA-1: `b2cddd1efb0f25f35a6a08354290f805812bf34c`.

Values remain:
- `live_trading_enabled: false`
- `FINAL_EXECUTION_AUTHORIZATION: false`
- `LIVE_EXECUTION: BLOCKED`
- `capital_plane_mode: VERIFY_ONLY`
- `research_capital_authority: false`

No order, proposal-to-buy, account mutation, deployment, secret read, or LIVE_LOCK modification was performed by this cycle. No strategy was promoted.
