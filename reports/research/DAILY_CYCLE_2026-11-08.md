# AURELIA Daily Research Cycle — 2026-11-08

**Research cut-off:** 2026-11-08 01:34 EAT (2026-11-07 22:34 UTC)  
**Market-data cut-off:** Friday 2026-11-06 US close; weekend snapshots are context only.  
**Canonical repository head inspected:** `main` at `d04564aca0648201feff0326fe9af0fbcee92e94`  
**Scope:** research, data-quality, engineering, security and governance review only.

## Executive disposition

- `DAILY_REVIEW=COMPLETE`
- `MODEL_TRAINING=NOT_RUN`
- `NEW_R100_HISTORICAL_CAMPAIGN=BLOCKED`
- `R100_V0_2_0=RETIRED_FROM_QUALIFICATION`
- `369_MSNR=RESEARCH_ONLY_UNQUALIFIED`
- `CI_CREDENTIAL_BOUNDARY=P0_REMEDIATION_OPEN`
- `EXECUTION_ECONOMICS=UNVERIFIED`
- `STRATEGY_PROMOTION=BLOCKED`

The highest-priority issue remains production credential isolation in the current `main` workflows. A separate research issue is that the archived R_100 OOS result is negative and poorly calibrated. No new strategy performance claim is supported.

## 1. Market intelligence

### US cash-market session

The connected Alpaca IEX daily-bar query returned five sessions for SPY, QQQ, DIA and GLD, but **zero bars for TLT and USO**. The panel is therefore incomplete; no TLT or oil ETF return is inferred.

| IEX instrument | Nov 6 vs Nov 5 | Nov 2–6 close-to-close |
|---|---:|---:|
| SPY | +0.269% | -2.213% |
| QQQ | +1.275% | -3.657% |
| DIA | -0.457% | -1.364% |
| GLD | -0.799% | +3.030% |
| TLT | No bars | No bars |
| USO | No bars | No bars |

These are IEX ETF observations, not consolidated SIP index returns, futures prices, or Deriv synthetic-index prices. QQQ is an ETF proxy for the Nasdaq-100, not the Nasdaq Composite. IEX trade counts and volume are not consolidated-market volume.

Reuters/AP reported the Friday close as S&P 500 +0.3%, Nasdaq Composite +1.1%, Dow -0.5%; the week remained negative for all three, with the S&P 500 down 2.7%, Nasdaq down 3.4% and Dow down 0.9%. The semiconductor index rebounded 4.2% Friday after the earlier-week technology selloff. This is consistent with a partial rebound, not proof that the correction ended.

**Broad-market regime:** `EVENT_DRIVEN_CORRECTION_WITH_PARTIAL_TECH_REBOUND` [Likely].  
**AURELIA R_100 regime:** `UNCLASSIFIED`. Broad equities and macro news are not validated predictive inputs for Deriv synthetic indices.

### Weekend cross-asset coverage

The weekend TickerLayer board returned recent crypto and FX observations, but gold, WTI, US500, US100 and US 10Y were unavailable under the connected plan. The NVDA observation was stale relative to the board timestamp. Those unavailable/stale fields were excluded from current-regime inference.

## 2. Global macro and news

### US October employment — released November 6

The BLS reported:
- Nonfarm payrolls: +165,000.
- Unemployment rate: 4.1%.
- Average hourly earnings: +0.4% m/m and +3.1% y/y.
- U-6 underemployment: 7.9%, up from 7.6% in September.
- Part-time employment for economic reasons: +339,000 to 4.8 million.
- August and September payroll estimates revised up by a combined 84,000.

The headline payroll gain is stronger than expected; the rise in U-6 and involuntary part-time work makes the labour signal less uniformly strong. Reuters reported that market-implied odds of a December Fed rate increase rose to roughly 75–78% after the report. This is market pricing, not a Federal Reserve commitment or official forecast.

### Other central-bank context

The Bank of England raised Bank Rate by 25bp to 4.00% on November 5, in an 8–1 vote. Energy-driven inflation risk remains a policy concern. The RBA's November 3 cash-rate increase to 4.85% is also part of the current global tightening context.

### Next material release

US October CPI is scheduled for **Tuesday, November 10, 2026, at 08:30 America/New_York (16:30 EAT)**. Treat this as a scheduled event-risk window; do not encode the event as a directional R_100 feature without a pre-registered, instrument-specific test.

US session code must use `America/New_York`, not a fixed UTC offset.

## 3. Archived R_100 campaign: independent artifact recalculation

I downloaded the preserved GitHub Actions artifact for offline analysis only.

- Artifact ID: `13130052450`
- Source run: `41420980026`
- ZIP SHA-256: `a433bbc8a257e4abc22ef1713cbb1cf1b533541d3624528eedbd4ac90be242ed`
- Embedded state SHA-256: `e120937647ccf31a954a7ba38bb1366845468714f1d4750c9ceab3eefeb31058`
- Experiment: `R100-PROSPECTIVE-20261008T192038Z`
- Hypothesis: `H-R100-TICK-MOMENTUM-001`
- Strategy: `R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0`
- Frozen source commit: `67922e738acd06e9f77d434819df1a56aa11974d`
- Config hash: `cca748c28c1253bf047743c46a208e114c6ade2601fb5aa5bbedcc2dcfa2ad15`

The ZIP hash and embedded state hash match the hashes preserved in PR #285. Recalculation was performed from the extracted observation and quote records; it is not a new live feed campaign or source-tape replay.

### OOS metrics

| Metric | Recalculated result |
|---|---:|
| Total observations | 783 |
| In-sample observations | 170 |
| OOS observations | 613 |
| OOS wins | 311 |
| OOS hit rate | 50.7341% |
| Wilson 95% interval for hit rate | 46.7842%–54.6749% |
| Mean predicted probability | 64.7157% |
| Mean probability overstatement | 13.9816 percentage points |
| Brier score | 0.270921 |
| Constant-base-rate Brier | 0.249946 |
| Brier skill vs constant base rate | -8.3916% |
| Archived payout/stake ratio | 1.95 |
| Quoted break-even probability | 51.2821% |
| Mean quoted net return per stake | -1.0685% |
| Mean direction-adjusted underlying return | +0.01265% |

All 613 OOS observations had a matching archived quote record. The quote ratio was 1.95 in the archived sample. These are historical proposal quotes, **not verified fills**; they do not establish realized slippage, spread at execution, commission, latency or realized contract P&L.

The positive mean direction-adjusted underlying return is not contract profit and does not override the negative quoted contract result.

### Calibration

| Predicted-probability bucket | OOS n | Mean predicted | Realized hit rate | Absolute gap |
|---|---:|---:|---:|---:|
| 0.60–0.65 | 396 | 63.5914% | 51.7677% | 11.8237 pp |
| 0.65–0.70 | 209 | 66.6161% | 49.2823% | 17.3338 pp |
| 0.70–0.75 | 8 | 70.7224% | 37.5000% | Non-qualifying sample |

Only two buckets meet the 10-observation minimum; the frozen campaign policy requires at least three qualifying buckets and a maximum reliability gap of 5%. Calibration fails.

### Dependence-aware resampling and tail diagnostics

A moving-block bootstrap was run on the frozen 613-observation OOS quoted net-return sequence, with 20,000 resamples per block length and fixed seed `20261108`. Block lengths were 1, 5, 10, 20 and 40 observations.

- The 95% bootstrap interval for mean net return per stake ranged approximately from **-9.02% to +6.88%** across the block-length sensitivity set.
- Every interval includes zero; this sample does not establish positive net expectancy.
- In the observed OOS ordering, the cumulative quoted net result was **-6.55 stake units**, maximum peak-to-trough drawdown was **26.70 stake units**, and the longest losing streak was **11**.
- A separate 5,000-path block-resampling sensitivity at block lengths 10, 20 and 40 produced broad terminal-P&L intervals spanning negative and positive values; the upper 97.5th-percentile maximum drawdown was approximately 62–66 stake units.

These are resampling diagnostics of one short historical OOS sequence, not a calibrated future-loss probability, account-level drawdown forecast, or qualification-grade Monte Carlo. No account equity, verified contract maximum-loss mapping, or full tick tape is present.

### Campaign lifecycle

The embedded manifest remains `sealed=false`. It contains one pending signal at age 6 ticks. Last collection completed at `2026-10-15T16:28:53Z`, approximately 2h51m45s before the planned campaign end at `2026-10-15T19:20:38.482344Z`. The archive does not contain the complete original tick tape.

A **disposable-copy dry-run** of the expiry-sealer logic from PR #289 returned `SEALED_WITH_UNRESOLVED_PENDING` for this copy:
- 783 observations retained.
- The pending signal remained unchanged and unresolved.
- Historical observations and quote rows were unchanged.
- Report qualification changed to `NOT_RECALCULATED_AFTER_EXPIRY`.
- `strategy_live_eligible=false`, `execution_authorized=false`, `capital_authority=false`, `live_execution=false`.

This was not a repository write, not a merge, and not a seal of the original artifact or main-branch state. The sealer was exercised in an isolated harness with helper imports stubbed; exact integrated branch CI and review remain necessary.

**Decision:** keep `R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0` retired from qualification. Preserve the archive. Do not backfill the pending signal, retune the model, or reuse this OOS set.

## 4. Repository and security audit

### Canonical main

Inspected `main` at `d04564aca0648201feff0326fe9af0fbcee92e94`.

Current `config/LIVE_LOCK.yaml`:
- Git blob SHA-1: `b2cddd1efb0f25f35a6a08354290f805812bf34c`
- Raw-file SHA-256: `72a8e51129a4dd6f7bac1ccb5b181c7b0c8b0d1fc16933ca61ffe349a0c1d6b7`

Current values remain:
- `live_trading_enabled=false`
- `FINAL_EXECUTION_AUTHORIZATION=false`
- `LIVE_EXECUTION=BLOCKED`
- `capital_plane_mode=VERIFY_ONLY`
- `research_capital_authority=false`

### P0: current main still has untrusted CI credential paths

Direct main-branch inspection found:
1. `.github/workflows/aurelia-assurance.yml` is triggered by `pull_request`, selects the `production` environment and maps Deriv credential secrets into the general Assurance job.
2. `.github/workflows/aurelia-free-runtime.yml` contains a 15-minute schedule and credential-bearing authenticated jobs.
3. `.github/workflows/deriv-auth-evidence.yml` contains a six-hour schedule and Deriv credential mappings.
4. `runtime/agent_workers.py` still launches configured commands with `asyncio.create_subprocess_exec(*command)` and no explicit sanitized environment mapping, so child processes inherit the parent environment.

The schedule declarations do not prove that the workflows are currently enabled. Their source configuration nevertheless permits the scheduled credential-bearing paths on current main.

### PR #292 — critical CI credential isolation

- Head: `31714cd9f0cb02a847d900681936745b5add52e7`
- Exact-head Assurance run `42411091315`: passed.
- Agent Federation Audit `42411091218`: passed.
- Agent Continuity Watchdog `42411091211`: passed.
- 8 changed files; general Assurance no longer selects production or references secrets.
- Protected authenticated/lifecycle/deployment/WhatsApp jobs are gated to manual dispatch from `refs/heads/main`.
- Six-hour scheduled Deriv auth evidence trigger is removed.
- Regression tests cover the general Assurance boundary and protected job trigger conditions.

PR #292 remains open, draft and without a formal review submission. A repository audit comment reports that branch protection requires one approving review; it also reports that the Vercel check is not a required status. The Vercel error must not be bypassed or treated as a security approval.

The PR leaves protected secret-bearing jobs available on trusted main/manual dispatch and a main-only secret-presence report. Do not dispatch authenticated Deriv/account, lifecycle, deployment or messaging jobs as part of this research cycle. Deriv account endpoints require `trade` scope; that is not a genuinely read-only account permission.

**Current main remains exposed until a reviewed security fix is merged.** The passing PR branch does not retroactively protect main.

### Other relevant PRs

| PR | Exact-head evidence | Disposition |
|---|---|---|
| #289 — disable public proposal quotes and harden R_100 expiry sealing | Assurance, Deriv Credential Boundary Audit and public CI passed | Draft, unmerged, no formal review; main collector still contains proposal logic |
| #290 — read-only governance audit | Federation and Watchdog passed; Assurance failed at authenticated Deriv session; PR description says its unit tests were not executed in a repository runtime | Draft, unmerged |
| #291 — 369/MSNR research implementation | Federation and Watchdog passed; Assurance failed at authenticated Deriv session on the remote branch head | Draft, unmerged |
| #285 — preserve negative R_100 OOS evidence | Historical artifact and recalculation lineage recorded | Draft, unmerged |

The owner reports that an isolated Vercel sandbox snapshot for #291 has 52 focused 369/MSNR tests, 132 research/lab tests, 63 Assurance tests and 533 full-repository tests passing. That snapshot has **not** been pushed to the PR branch; it is not remote branch CI and is not a mergeable source revision.

### Corrected canonical probability policy

A direct main read of `runtime/core/authority.py`, `config/runtime.yaml` and `AURELIA_SOURCE_OF_TRUTH.json` confirms the canonical policy is **0.50–0.75, inclusive, no clipping**. The earlier report's claim that 0.55 was already canonical was incorrect. The 0.55–0.75 change remains a proposal, not the current main policy.

### Missing main-branch evidence

The following paths return `NOT_FOUND` on main:
- `data/raw/r100_1m.csv`
- `data/frozen/r100_dual_resolution_manifest.json`
- `config/costs.yaml`
- `research/aurelia_r100_state.json`

The current strategy registry contains nine entries: four `RESEARCH_ONLY_UNQUALIFIED` and five `BLOCKED_IMPLEMENTATION_NOT_VERIFIED`. All nine have unknown cost profiles and OOS/walk-forward/calibration/net-economics/robustness/uncertainty/forward-test/soak states not run. The 369/MSNR candidate is not yet registered on main.

## 5. Research-domain coverage

| Domain | Current disposition |
|---|---|
| Market structure / BOS / MSS / protected swings | Deterministic code exists; no new verified R_100 performance evidence |
| Liquidity sweeps / reclaim | Candle-derived proxy only; no resting-liquidity evidence |
| Fair-value gaps / midpoint mitigation | Candidate logic; no cost-adjusted expectancy |
| Opening-range / consolidation breaks | Session metadata and synchronized M1/M15 evidence absent |
| Trend / momentum | Archived v0.2.0 is adverse; no new controlled R_100 sample |
| Mean reversion | No controlled comparison against trend/momentum |
| Volatility / tick dynamics | No new source-bound R_100 tick tape; tick count is not true volume |
| Multi-timeframe | M15 sweep → closed M1 MSS → aligned first FVG midpoint retest remains a hypothesis |
| Microstructure | No true DOM, CVD/delta, aggressor-side tape or order-book evidence |
| ML / feature engineering | No new training; deterministic baseline and leakage checks first |
| Probability / calibration / uncertainty | v0.2.0 calibration fails; block-bootstrap intervals include zero |
| Position sizing | No account evidence or verified maximum-loss/contract mapping |
| Drawdown / tail risk | Historical unit-stake drawdown only; no account-level risk simulation |
| Execution costs | `config/costs.yaml` absent; archived proposal quote is not a fill |
| Walk-forward / OOS | No new run; old v0.2.0 OOS must not be reused |
| Monte Carlo | Limited moving-block bootstrap only; no qualification-grade simulation |
| Ablation | Structure-only versus structure+369 remains first paired experiment |
| Parameter sensitivity | Not run |
| Multiple testing | Archived v0.2.0 had trial_count=1, search degrees of freedom=0, OOS reuse=0; new 369 variants must be pre-registered |
| Strategy retirement / revalidation | v0.2.0 retired; 369/MSNR remains unqualified |
| Engineering / risk | CI credential isolation, subprocess environment inheritance, transport/data provenance and costs remain blockers |

## 6. Ranked hypotheses and assignments

Assignments below are proposed ownership, not evidence of external agent execution.

| Priority | Hypothesis / repair | Primary | Independent challenge |
|---|---|---|---|
| P0 | Remove production credentials from pull-request CI; gate remaining secret jobs to trusted manual main only | ClaudeCode / repository security owner | GoogleAgentSkills, JEV, GLM |
| P0 | Replace inherited worker environment with an explicit allowlist; enforce provider identity and task/result protocol | ClaudeCode | GoogleAgentSkills, GLM |
| P1 | Integrate #289 expiry sealing without changing historical metrics or resolving the pending signal | ClaudeCode | JEV |
| P1 | Acquire and freeze date-scoped R_100 M1/M15 data with immutable hashes and continuity checks | ClaudeCode | JEV |
| P1 | Obtain source-backed instrument specification and itemized spread/slippage/commission/fee/latency evidence | ClaudeCode | JEV |
| P2 | 369/MSNR baseline: confirmed protected swing + closed-bar MSNR + [09:45,10:00) New York close + next-bar-open entry + >=3 gross-R target distance | KimiK3 | JEV, GLM |
| P3 | Structure-only versus structure+369 paired ablation | KimiK3 | JEV, GLM |
| P4 | Pre-registered displacement and EMA20/ATR14 variants with adequate warm-up | KimiK3 | JEV, GLM |
| P5 | Trend/momentum versus mean-reversion and opening-range baselines | KimiK3 | JEV |
| P6 | ML only after deterministic baseline, leakage, feature-stability, calibration and OOS gates | KimiK3 | JEV, GLM |

The remote #291 branch still has an EMA20/ATR14 warm-up check that allows computation with only 15 completed bars; the isolated snapshot reportedly changed this to 100 bars, but that change is not in the remote branch. The remote branch also adds timeframe duration to an aware timestamp without first normalizing to UTC; the isolated snapshot reportedly corrected this. Transfer those fixes only after the #292 credential boundary is reviewed and merged, then rerun exact-head CI.

GrokBot remains market-context/orchestration only. Layer 6 remains the deterministic risk veto. No external ClaudeCode, KimiK3, JEV, GLM, GrokBot, DeepSeek Harness or Hermes task execution was verified. The installed skill inventory returned no available entries in this run. GitHub, Alpaca, TickerLayer and web research were used; no Deriv account authentication was attempted.

## 7. Smallest safe repair sequence

1. Obtain independent formal security review and approval for #292. Do not bypass branch protection or the Vercel verified-commit policy.
2. Merge the credential-isolation repair only after required approval; then re-audit all workflow triggers, environments and secret references on the new main head.
3. Keep authenticated account/lifecycle/deployment/messaging workflows undispatched. Do not treat a `trade`-scoped credential as read-only.
4. Replace inherited worker subprocess environment with a minimal allowlist and authenticated provider protocol; keep provider execution disabled until independently verified.
5. Review and integrate #289 expiry sealer and proposal-disable policy; preserve pending signal and original metrics.
6. Transfer the tested 369/MSNR fixes from the isolated snapshot to a reviewed remote branch after the security gate; rerun exact-head CI.
7. Acquire and freeze valid R_100 M1/M15 history, source-verified instrument mapping and cost inputs.
8. Run a frozen structure-only baseline, then pre-registered ablations, WFA/OOS, calibration, dependence-aware uncertainty, Monte Carlo and multiple-testing correction.

## 8. Safety verification

- Main `config/LIVE_LOCK.yaml` was read; its blob SHA-1 and raw SHA-256 are recorded above.
- No LIVE_LOCK changes.
- No broker orders, proposals or account authentication were made by this cycle.
- No credential values were read or exposed.
- No deployments or capital actions.
- No strategy promotion.

**Final verdict:** the research review and archived OOS recalculation are complete. The security fix is available as a passing but unreviewed PR, not yet effective on main. R_100 historical data and execution economics remain blocked. The next useful work is credential-boundary review and data/cost provenance, not another strategy variant.
