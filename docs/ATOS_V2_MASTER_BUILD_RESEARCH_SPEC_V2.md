# ATOS v2.0 / AURELIA — Master Build & Research Specification v2.0

- **Status:** Owner-delegated governing research specification; supersedes v1.0 for Layer-9 research
- **Effective:** 2026-11-11
- **Execution mode:** RESEARCH-ONLY
- **Live state:** `LIVE_LOCK=ON`
- **Authority boundary:** This document governs the Layer-9 research programme only. It authorizes no live execution, capital movement, production architecture replacement, or change to `config/LIVE_LOCK.yaml`.

## 0. Role and evidence labels

ATOS v2.0 is the quantitative research programme implemented within AURELIA. Work must be evidence-based, reproducible, and decision-ready. Label claims as **FACT**, **ASSUMPTION**, or **OPINION**. Never fabricate data, results, citations, links, or tool activity. State uncertainty. Ask no more than one focused owner question per interaction.

## 1. Non-negotiable controls

1. **Layer 6 (L6) is the sole deterministic Risk Authority.** Only its versioned gate state machine may transition `LIVE_LOCK → SHADOW → CANARY → LIVE`. No LLM, agent, heuristic, operator shortcut, or strategy proposal can bypass it.
2. LLMs and agents are restricted to research, analysis, code review, and reporting with read-only access to results. They have zero capital, execution, secret, release, or risk authority and never participate in the order-execution or risk-decision path.
3. No strategy is promotion-eligible without a pre-registered hypothesis, versioned specification, explicit cost model, placebo/matched controls, and untouched out-of-sample evidence.
4. Secrets belong only in approved environment/secret stores. Never place them in code, chat, logs, reports, docs, or artifacts. Any Deriv credential used in a future, separately authorized workflow must be least-privilege; no payments/admin scope. Rotate on exposure. Never log PATs, OAuth tokens, OTPs, or authenticated URLs.
5. Report institutional metrics: expectancy in R with confidence interval, profit factor with confidence interval, max drawdown, Sharpe with HAC standard error, DSR, PBO, fill rate, MAE/MFE, placebo delta with confidence interval, and cost attribution. Win rate alone is not evidence.
6. Refuse requests that conflict with these controls and record the conflict.
7. This specification does not authorize live trading. Live capital, live risk limits, and any LIVE_LOCK change require explicit owner ratification and all applicable gates.

## 2. Canonical platform and implementation facts

- Repository: `Anto-30/aurelia-trading`; canonical branch: `main`.
- Implementation authority: `AURELIA_REPOSITORY_MAP.md` and `AURELIA_SOURCE_OF_TRUTH.json` on `main`. Historical branches are not implementation source of truth.
- AURELIA is a **fixed-payout Deriv Options platform** (RISE/FALL-style contracts), not a linear CFD/SL-TP engine.
- Owner-specified platform policy: probability band 50%-75% inclusive, no clipping; minimum contract/stake USD 1.00; live stake is 1% of fresh, verified USD balance, rounded down to cents; a 1% budget cannot fund USD 1 until verified USD balance is at least USD 100; non-USD or lower balances remain blocked. Strategies and agents cannot override deterministic sizing.
- The current release control is `config/LIVE_LOCK.yaml` and must remain unchanged by this research specification:
  - `live_trading_enabled: false`
  - `FINAL_EXECUTION_AUTHORIZATION: false`
  - `LIVE_EXECUTION: BLOCKED`
  - `capital_plane_mode: VERIFY_ONLY`
  - `research_capital_authority: false`
  - `external_repositories_capital_forbidden: true`
  - `blind_resubmission: false`
  - `kill_switch_independent: true`
- Canonical components include `capital/capital_plane.py`, `runtime/broker/executor.py` (single capital executor), `execution/deriv.py`, `runtime/adapters/*`, `runtime/core/{authority,capabilities,exposure,idempotency,fencing,reconcile,recovery,release_gate,health,supervisor,ledger}.py`, `runtime/security/secrets.py`, `runtime/validation/{walk_forward,probability,decision_replay}.py`, `runtime/strategy/governance.py`, `research/`, and `assurance/`.
- Deriv integration uses the current `api.derivws.com` API. Legacy `ws.derivws.com/Binary v3` is diagnostic-only and must never be a production fallback.

## 3. Governance and architecture

The canonical repository map and source-of-truth metadata remain implementation authority. This specification governs Layer-9 research only and does not create production layers.

ADR-001 maps the logical research responsibilities to existing components:

| Responsibility | Existing boundary |
|---|---|
| L0 governance/security | `runtime/security/`, `assurance/`, `config/` policies |
| L1 data | Research-side ingestion and ephemeral feed adapters |
| L2 features/regimes | Research-side modules |
| L3 strategy zoo | `research/` plus `runtime/strategy/governance.py` |
| L4 portfolio/allocation | Research-side simulation only |
| L5 execution semantics | `execution/`, `runtime/broker/`, `runtime/adapters/` as offline simulation/replay contracts only |
| L6 risk authority | `capital/capital_plane.py`, `runtime/core/` controls, release gate, and LIVE_LOCK |
| L7 monitoring/ops | `runtime/core/health.py`, `runtime/core/supervisor.py`, `runtime/ops/` |
| L8 journal/reporting | `reports/` and `runtime/core/ledger.py` |
| L9 research engine | `research/` and `runtime/validation/` |
| L10 AI orchestration | Research-only, read-only |

Do not implement the proposed layer model as a new production architecture. Record every architecture or specification change in a numbered ADR with rationale, alternatives, and owner-ratification status. L6 remains the sole deterministic risk authority; `runtime/broker/executor.py` remains the single capital executor.

## 4. Instruments and sequence

Research priority: **(1) EURUSD, (2) XAUUSD, (3) NQ futures and Indian index options as secondary research**.

Resolve exact Deriv symbols through a current `active_symbols` response; never guess symbol codes. Verify account/product eligibility and applicable jurisdiction before any separately authorized automation. Exclude all Deriv synthetic indices (including R_100) from FX order-flow/SMC research. Quarantine all R_100 artifacts, including outputs of `research/r100_prospective_oos_archiver.py`; they are not evidence for the FX programme.

## 5. Data architecture

### 5.1 Persistent research archive

Persistent archives may use only sources whose license permits the intended internal research use.

- **Primary candidate: TrueFX / Integral.** The owner-reviewed terms permit historical FX data use for internal purposes such as viewing and analysis and prohibit redistribution/dissemination of content, including prices. Registration is required. EURUSD is the first instrument. Confirm history depth, exact symbol list, export format, and parser schema after registration. XAUUSD/metals coverage remains unverified until the registered account's instrument list is inspected.
- **Dukascopy web export:** the conservative reading of website terms permits personal non-commercial download but prohibits constructing/storing a database from website content. Do not build a persistent archive from the web export. Gold archive remains blocked until JForex client-agreement data terms are verified or written permission is obtained.
- **HistData.com:** HOLD. Do not ingest until terms covering internal use, storage, and backups are confirmed in writing.
- This is a conservative compliance reading, not legal advice. When terms are ambiguous, the restrictive reading governs until clarified in writing.

### 5.2 Deriv API data

Treat Deriv API-derived market content as ephemeral. The owner-reviewed API terms prohibit storage of API-derived content, permit caching up to 24 hours, and require deletion on termination. Enforce a TTL no longer than 24 hours with automated expiry/deletion. Never persist raw Deriv candles, ticks, or price-level ledgers to Git, long-lived CI artifacts, or cloud storage. Persist only aggregate results and provenance (source, request parameters, retrieval time, code/version, and permissible checksums). Flag API Terms §3.1.6 IP-assignment language for qualified legal review before productization.

### 5.3 Cross-source calibration

TrueFX/Integral, Dukascopy, and Deriv represent different liquidity pools/quote environments. Before trusting any level-based signal across venues, quantify price/spread divergence on overlapping recent windows and record timestamp alignment, instrument basis, bid/ask-vs-mid basis, spread differences, gaps, transformations, and uncertainty. Fail closed if feeds are not comparable for the hypothesis. A signal present on only one feed is a possible feed artifact, not an edge.

### 5.4 Data quality

Require gap, stale-tick, duplicate, and outlier detection; weekend/holiday filters; IANA timezone/DST handling (never fixed UTC offsets); exchange/session calendars; timestamp alignment; documented bid/ask-vs-mid basis; and explicit truncation detection. NQ needs documented futures roll and back-adjustment policy. Never silently accept truncated data.

### 5.5 Provider limits

Provider limits must be verified at run time. Owner-specified working limits include: yfinance intraday 1m approximately up to 7 days per request and approximately 30 days total; 5m/15m approximately up to 60 days; 1h approximately up to 730 days. Owner-specified Deriv ceilings are 220/minute and 14,400/hour for WebSocket `ticks_history` under the all-other-calls budget; REST ceilings are 300/minute/IP, 1,000/10 minutes/IP, and 80/minute/logged-in user. The new API `ticks_history` default count is 1,000 (legacy 5,000); pass `count` explicitly. Treat these values as operational hints, not immutable guarantees: confirm current provider limits at run time, pace requests, reuse a connection, honor rate-limit rejections, and back off.

### 5.6 Reproducibility

Pin licensed archive snapshots by content hash; version ingestion code; fix random seeds; lock the environment; use deterministic replay; require exact-head CI. Backups of licensed archives must respect the source license and internal-use restrictions. Hashes/provenance must not be used to reconstruct or distribute restricted source content.

### 5.7 Feed semantics

Deriv FX does not provide DOM or exchange true volume. Do not claim OFI, VPIN, or true-volume features from candle/tick data. Tick imbalance and realized volatility are proxies and must be named as such. Use explicit spread, slippage, and commission assumptions with sensitivity ranges.

## 6. Strategy registry

### 6.1 MSNR

MSNR is the owner-defined core strategy, but exact entry, exit, invalidation, timeframe, session, and risk rules have not yet been supplied. Treat it as a placeholder. Do not invent or code a presumed MSNR.

### 6.2 OB+FVG v0.1 — Track A

Track A is a linear price-signal study, venue-agnostic and **non-executable** on the fixed-payout capital plane unless a separately approved execution-mapping gate passes. All numeric defaults are proposals and must be frozen in G0:

- 1H context: untouched buy-side/sell-side liquidity levels.
- 15m/5m trigger: prior liquidity sweep (wick through, body close back inside).
- Displacement: at least 3 consecutive candles, each range at least 1.5 × ATR(14) by default; sequence closes through last confirmed swing (MSS).
- OB: last opposing-colour candle before impulse; zone is candle body only.
- Require an unfilled bullish/bearish FVG created by the impulse.
- Require an untouched opposing liquidity target; otherwise SKIP.
- Entry at 50% of OB body. Passive fill requires trade-through, not touch. No chase. Cancel unfilled limit after 12 bars by default or on structure invalidation.
- Stop beyond OB wick plus 0.1 × ATR buffer by default.
- Exit on entry-timeframe body close beyond midpoint; hard stop is a backstop; TP at opposing liquidity. Short logic mirrors long logic.
- Model adverse selection, spread, slippage, partial/non-fill outcomes, and alternative cost/fill assumptions. Session filter must use pre-registered killzones.

### 6.3 OB+FVG — Track B

Track B maps Track-A signal quality into calibrated directional probabilities at fixed horizons using triple-barrier labels, then evaluates expected value against fixed-payout payoff net of costs. Any mapping must respect the platform's 50%-75% inclusive probability band, USD 1 minimum contract, 1% deterministic sizing policy, and USD 100 minimum balance for the minimum live stake. Validate calibration with reliability analysis and Brier score. Track B is research-only and does not authorize live contracts.

### 6.4 3-6-9 hypothesis

Quarantined; no live use. 08:49:55 New York is an unverified hypothesis only. Tests are restricted to: (i) fixed-time feature versus placebo times, (ii) post-08:30-news drift, and (iii) spectral peak versus a suitable red-noise null. Numerology is not a mechanism.

### 6.5 Mandatory baselines

For every strategy: random-entry/same-exit, matched placebo zones (same size/distance/direction), shuffled-signal permutation, and buy-and-hold where appropriate. Credit a setup only for incremental edge above the relevant placebo baseline. Barrier-hit baselines are not assumed to equal 50%. The owner-supplied prior measurements are approximately 47.3%-52.3% overall and 43.3%-54.6% by direction; treat them as empirical context, not universal constants. Use matched controls for each experiment rather than win-rate intuition.

### 6.6 Evidence prior

The owner-supplied evidence prior reports no reliable OB edge versus matched placebo across 31 runs/~1,854 zones; displacement/body-only filters did not improve results beyond noise; reversal-as-taught SMC claims are unsupported in the cited experiments (sweeps were reported as predicting continuation); and a separate 10-year GBPUSD OB backtest reported PF 0.83 / 38% win under a different exit. That GBPUSD result is illustrative only, not directly comparable. These are research priors, not proof about every variant. The burden of proof remains on the proposed setup. The core asset is the validation machine, not any particular strategy.

## 7. Validation gates

L6 owns the state machine: `LIVE_LOCK → SHADOW → CANARY → LIVE`; any breach causes immediate downgrade. Numeric thresholds below are proposals unless separately ratified and pre-registered.

- **G0 — Pre-registration:** hypothesis ID, strategy version, parameters, instrument/timeframe/session, data lineage, cost model, baselines, one primary endpoint, success criteria, seed, and source commit. One primary hypothesis per experiment; no HARKing.
- **G1 — Sanity:** detector unit tests, human chart audit, and look-ahead lint. Statistical results do not replace chart review.
- **G2 — In-sample:** purged/embargoed CPCV, placebo, full costs, and expectancy confidence interval above zero.
- **G3 — Generalization:** walk-forward plus untouched holdout; DSR with defensible trial count; proposed PBO < 0.2; SPA/Reality Check versus baselines; parameter stability.
- **G4 — SHADOW:** proposed at least 100 live-paper trades; sequential evidence of positive expectancy after costs; uptime at least 99%; zero reconciliation breaks.
- **G5 — CANARY:** proposed risk no greater than 0.1% per trade; at least 50 trades; metrics consistent with G3 within bootstrap noise; explicit logged Risk Authority sign-off.
- LIVE only after G0-G5 are logged and signed. Re-run G3 quarterly or on drift alert.

Use stationary-bootstrap confidence intervals; HAC/Newey-West Sharpe standard errors; DSR/PBO/SPA with documented assumptions/trial counts; and sequential evidence methods (e-values/confidence sequences) only with stated assumptions. Maintain a trial-count ledger (every backtest run is a trial for DSR), enforce statistical power and minimum-detectable-effect requirements, reject underpowered samples, and maintain a negative-results registry. A proposed threshold is not a fact merely because it appears in this specification. The PBO <0.2 and G4/G5 sample/uptime values are proposed thresholds requiring owner/risk ratification.

## 8. Risk Authority research defaults

Research-simulation proposals only: per-trade risk ≤0.5%; ≤0.25 Kelly after estimation haircut; daily stop −2R; weekly stop −5R; drawdown breaker −10%; correlation/exposure caps; independent deterministic kill switch. These do not override current L6 configuration or LIVE_LOCK and are not approved live operating limits. Live capital and live limits require explicit owner ratification.

## 9. Execution and reliability — simulation only

Use one deterministic event-driven simulation semantics shared with any future execution contract; no vectorized/live semantic drift. Require deterministic replay, fixed seeds, look-ahead lint in CI, point-in-time joins, property-based indicator tests, explicit NaN/gap policy, DST-aware calendars, futures rolls, and immutable provenance. Model passive fills conservatively (trade-through, not touch), adverse selection, partial fills, session/volatility-dependent slippage, idempotent order IDs, reconnect/reconciliation semantics, clock synchronization, and latency budgets in simulation. This specification authorizes no live execution code changes, broker authentication, or order submission.

## 10. Security and compliance

P0 before any research rerun:

- Disable/fix command injection in `.github/workflows/atos-v2-smc-baseline.yml` caused by workflow_dispatch inputs interpolated into shell. Inputs must not be interpolated into `run:` source; if a future workflow requires inputs, pass them through step-scoped environment variables, validate strict formats, and add regression tests.
- Resolve PR #292 so production credentials are not exposed to untrusted CI refs.
- Treat workflow injection as blocking. Deriv API Terms §8.2 is identified by the owner as allowing suspension of apps with security vulnerabilities; verify the current clause before relying on it.
- Pin dependencies, apply least privilege, and prohibit secrets in logs/artifacts.
- Verify Deriv product/jurisdiction terms and applicable local requirements. Verify current SEBI/NSE requirements before any Indian-market automation. Jurisdiction is an open owner input and must not be inferred from location metadata. This is not legal advice.

## 11. ML and AI rules

Frame filters as meta-labeling: triple-barrier labels are primary; secondary model may size/skip. Use purged CV plus embargo, sample-uniqueness weights, conformal prediction intervals, and model registry/drift tests. No model promotion before G2-G3. RL/deep hedging remain research backlog. LLM agents are research/review/report-only and read-only.

## 12. Monitoring and model-risk governance

Research design includes sequential tests using e-values/confidence sequences; CUSUM/Page-Hinkley and ADWIN drift detection; auto-degrade to SHADOW on breaches only through L6 authority; uptime/latency/alerting; incident log and postmortems. Maintain SR 11-7-style model-risk governance: model inventory, independent validation, challenger models, documented assumptions/limitations, and challenger-model outcomes.

## 13. Reporting contract

Every experiment reports: hypothesis ID; spec version; instrument/timeframe/session; data lineage and snapshot hash; number of trades; fill rate; expectancy (R) with 95% stationary-bootstrap CI; PF with CI; max DD and ulcer index; Sharpe with HAC SE; DSR; PBO; placebo delta with CI; cost attribution (spread/slippage/fees); MAE/MFE; regime breakdown; sensitivity grid; gate verdict; next action. Maintain decision log and numbered ADRs. Do not report vanity metrics as evidence.

## 14. Research discipline

Pre-register primary endpoints; one primary hypothesis per experiment; log every trial in the DSR ledger; record negative results; enforce power/MDE minimums; set time/compute budgets and stop rules; version the specification and changelog. Prefer falsifying weak ideas quickly over endless tuning.

## 15. Prioritized backlog

- **P0:** workflow shell-injection remediation and PR #292 security isolation; confirm owner ratification of design selections and proposed numbers.
- **P1:** TrueFX registration and history/coverage/schema verification; L1 ingestion and quality gates; cross-source calibration gate; G0 pre-registration and G1 detector tests/chart audit for OB+FVG v0.1 on EURUSD.
- **P2:** placebo/matched-control framework; G2; Track-B contract/payoff mapping research.
- **P3:** XAUUSD archive via approved Dukascopy permission/JForex route; meta-labeling filters; regime gating; sequential monitor; portfolio allocation; Indian-options data/regulatory feasibility.

## 18. Owner-delegated design selections

These selections are research/architecture authority only and do not unlock capital or change LIVE_LOCK:

| Decision | Selection | Boundary |
|---|---|---|
| D1 Governance | Canonical AURELIA map on main is implementation authority; this specification governs Layer-9 research; architecture changes require ADRs | No new production layer model |
| D2 Data | TrueFX candidate for persistent EURUSD research; Deriv ephemeral ≤24h; Dukascopy gold conditional; HistData held | Verify registered-account coverage/schema before ingestion |
| D3 Sequence | EURUSD → XAUUSD → NQ/India secondary research | No symbol-code guessing or jurisdiction inference |
| D4 Strategy | OB+FVG Track A linear research plus Track B fixed-payout mapping; MSNR remains owner-rules placeholder | Track A is not executable on options plane; Track B remains research-only |
| D5 Validation | Placebo/matched controls, CPCV, DSR/PBO/SPA, bootstrap, trial ledger, power/MDE | No promotion absent G0-G5 and independent gate authority |
| D6 Risk envelope | Research simulation proposals: ≤0.5%/trade, ≤0.25 Kelly after haircut, −2R daily, −5R weekly, −10% DD breaker | Not approved live limits; L6 remains authoritative |
| D7 Security | Fix/disable workflow injection and resolve PR #292 before research reruns | Do not expose production credentials to untrusted refs |
| D8 AI boundary | LLMs/agents research, review and reporting only, with read-only results | Zero capital, execution, secrets, release or risk authority |

## 19. Key references — verify bibliographic details before use

The following are research references to verify and cite accurately when relevant. Their inclusion is not evidence that any ATOS strategy works: López de Prado (2018), *Advances in Financial Machine Learning*; Bailey and López de Prado (2014), Deflated Sharpe Ratio; Bailey et al. (2015), Probability of Backtest Overfitting; White (2000), Reality Check; Hansen (2005), Superior Predictive Ability; Newey and West (1987), HAC covariance estimation; Politis and Romano (1994), stationary bootstrap; Lo (2002), Sharpe ratio statistics; Howard et al. (2021) and Ramdas et al. (2023) on confidence sequences/e-values; Torrence and Compo (1998) and Mann and Lees (1996) on spectral significance/red-noise testing; Kelly (1956); Rockafellar and Uryasev (2000); Artzner et al. (1999); Ledoit and Wolf (2004); Bifet and Gavaldà (2007); Angelopoulos and Bates (2021); and Federal Reserve SR 11-7 (2011).

## 16. Interaction protocol

Lead with decision. Structure: verdict, reasons, risks/trade-offs, alternatives, next step. Use FACT/ASSUMPTION/OPINION labels. One focused owner question maximum. Refuse rule-breaking requests and document the conflict. Never claim file/tool access or implementation not supported by evidence. Separate completed implementation from assumptions and open gates.

## 17. Open owner inputs

Only the owner can supply or ratify:

1. Exact MSNR entry, exit, invalidation, timeframe, session, and risk rules.
2. Approved live capital amount and live risk limits.
3. Deriv account product type and applicable jurisdiction. Do not infer jurisdiction from location metadata.
4. Whether Indian-options automation is intended or the work is research-only.
5. Ratification or amendment of selected design decisions and proposed numeric thresholds.
6. TrueFX registration evidence: exact instrument list, available history depth, export format, and one representative CSV header line. No ingestion before this verification.

## Changelog

- **v2.0 — 2026-11-11:** supersedes v1.0; adopts EURUSD-first licensed data research; synthetic-index quarantine; separate OB+FVG Track A and fixed-payout Track B; mandatory placebo and cross-source calibration; trial ledger, negative-results registry, power/MDE and reporting requirements; preserves the existing AURELIA architecture and L6/LIVE_LOCK authority boundaries.
