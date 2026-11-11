# ATOS v2.0 — Master Build & Research Specification v1.0

Status: OWNER-SUPPLIED GOVERNING SPECIFICATION
Execution mode: RESEARCH-ONLY
LIVE_LOCK: ON
Effective date: 2026-11-11

This document is the governing owner-supplied research specification. It supersedes conflicting assumptions in earlier experimental SMC branches. It does not itself authorize implementation in production or live execution.

## 1. Authority and non-negotiable controls

- Layer 6 is the sole deterministic Risk Authority. Only its versioned gate state machine may transition LIVE_LOCK -> SHADOW -> CANARY -> LIVE.
- LLMs and agents are restricted to research, analysis, code review and reporting. They cannot set risk state, size capital, authorize, submit, amend or cancel live orders.
- No strategy can be considered for promotion without a pre-registered hypothesis, versioned specification, cost model, placebo/matched controls and untouched out-of-sample evidence.
- Secrets must remain in an approved environment/secret store; never in code, chat, logs, reports or documentation. Deriv scopes, if later required, must be least privilege and never payments/admin.
- Report expectancy in R, PF, max drawdown, Sharpe/DSR, fill rate, MAE/MFE and uncertainty intervals. Win rate alone is not evidence.
- If a requested action conflicts with these controls, refuse that action and document the conflict.

## 2. Confirmed and proposed architecture

Confirmed: Layer 6 Risk Engine; Layer 9 Python Research Engine.

Proposed until reconciled against the actual owner-approved layer map:
- L0 Governance/security/model risk
- L1 point-in-time market data, calendars, IANA time zones, quality gates and cost inputs
- L2 features and regimes
- L3 versioned strategy zoo
- L4 portfolio and allocation research
- L5 execution research/simulation only
- L6 deterministic Risk Authority (confirmed)
- L7 monitoring and operations
- L8 immutable trade journal and reporting
- L9 hypothesis registry, event-driven backtesting, look-ahead lint, purged CV/embargo, placebo controls, bootstrap inference, DSR/PBO/SPA, walk-forward and experiment provenance (confirmed)
- L10 research-only AI orchestration

Do not implement proposed layers as production architecture until reconciled with the actual specification.

## 3. Instruments and data

Primary research: XAUUSD and EURUSD via Deriv, subject to live active-symbol discovery, account/jurisdiction eligibility and data availability verification. NQ futures and Indian index options are secondary research only.

Exclude Deriv synthetic indices from all FX order-flow and SMC strategy tests. Synthetic indices are not proxies for real FX participant order flow.

Use Deriv public market-data WebSocket only for unauthenticated research. Resolve exact symbols via `active_symbols`; do not guess symbol codes. The current Deriv API documentation describes `ticks_history` candle granularity options including 60 seconds and an explicit count; test history depth, request limits and rate limiting before any multi-month run. Deriv API terms prohibit indefinite storage of API-derived content and permit caching for up to 24 hours only. Enforce deletion/expiry within that window; do not persist raw candles or price-level ledgers to Git, long-lived CI artifacts or cloud storage.

Yahoo Finance intraday constraints must be checked against current provider limits at run time. Do not assume 90 days of 1-minute data is available. Never silently accept truncated data.

Deriv FX has no DOM or exchange-traded true volume. Do not claim OFI/VPIN or true-volume features from candle/tick data. Tick imbalance and realized volatility are proxies only and must be named as such. Use explicit spread/slippage/commission assumptions and sensitivity ranges when executable quotes are unavailable.

## 4. Strategy registry

### 4.1 MSNR
Owner-defined strategy. Exact entry, exit, invalidation, timeframe, session and risk rules have not been supplied in this specification. Treat as a placeholder. Do not invent rules or code a presumed MSNR.

### 4.2 OB+FVG v0.1
All numerical defaults below are proposed and require pre-registration before testing.

- 1H context: untouched buy-side/sell-side liquidity levels.
- 15m or 5m trigger: sweep of a prior liquidity level with wick through and body close back inside.
- Displacement: at least three consecutive candles; each range >= 1.5 * ATR(14) by default; sequence closes through the last confirmed swing (MSS).
- Order block: last opposing-colour candle before the impulse; zone is candle body only.
- Require a bullish/bearish FVG created by the impulse and still unfilled at signal time.
- Require an untouched opposing liquidity target. Otherwise skip.
- Entry: 50% of OB body. Passive fill requires trade-through, not a touch. No chase.
- Cancel unfilled limit after 12 bars by default or on structure invalidation.
- Stop beyond OB wick plus 0.1 * ATR buffer by default.
- Exit on entry-timeframe body close beyond the midpoint; hard stop remains a backstop; TP at opposing liquidity.
- Model adverse selection, spread, slippage and limit non-fill. Include alternative cost/fill assumptions.

### 4.3 3-6-9
QUARANTINED. No live use. Treat 08:49:55 New York as an unverified hypothesis, not a fact. Test fixed-time feature against placebo times, post-08:30-news drift and spectral peaks against an appropriate red-noise null. Numerology is not a mechanism.

### 4.4 Mandatory baselines
For every strategy: random-entry/same-exit, matched placebo zones, shuffled-signal permutation and buy-and-hold where appropriate. Evidence must demonstrate edge above the relevant baseline.

## 5. Layer 9 validation

Every experiment must register hypothesis ID, strategy version, parameters, instrument, timeframe, sessions, data lineage, cost model, baselines, success criteria, seed and source commit before the run.

Required sequence:
- G0 pre-registration
- G1 detector tests and human chart audit
- G2 in-sample + purged/embargoed CPCV, placebo and full costs; expectancy CI > 0
- G3 walk-forward + untouched holdout; DSR at defensible trial count, proposed PBO < 0.2, SPA/Reality Check against baselines, parameter stability
- G4 SHADOW: proposed >=100 live-paper trades, sequential evidence that expectancy > 0 after costs, >=99% uptime and zero reconciliation breaks
- G5 CANARY: proposed <=0.1% risk/trade and >=50 trades, metrics consistent with G3 within bootstrap uncertainty, explicit Risk Authority sign-off
- LIVE only after all gates are logged and signed. Re-run G3 quarterly or after drift alerts.

Use stationary-bootstrap confidence intervals, HAC Sharpe standard errors, DSR/PBO/SPA where assumptions and trial counts are documented. No threshold is a fact merely because it appears here; all proposed numeric thresholds require owner/risk approval and pre-registration.

## 6. Risk Authority proposed defaults (not approved operating limits)

- Per-trade risk <=0.5%
- <=0.25 Kelly after estimation haircut
- Daily stop -2R; weekly stop -5R
- Drawdown breaker -10%
- Correlation/exposure constraints and deterministic kill switch

These are proposed research values only. They do not supersede the existing AURELIA LIVE_LOCK or Layer 6 settings without formal governance approval. Live remains BLOCKED.

## 7. Research engineering and AI boundaries

Prefer a single deterministic event-driven simulation semantics for research and any future execution implementation. Require deterministic replay, fixed seeds, look-ahead lint, point-in-time joins, property-based tests, explicit NaN/gap policy, DST-aware calendars, futures rolls and immutable provenance.

ML is secondary: meta-labeling with triple-barrier primary labels, purged CV/embargo, sample-uniqueness weights, conformal intervals and model registry/drift tests. RL/deep hedging remain backlog research only. No model promotion without G2-G3.

AI agents may research, review code and draft reports against read-only result access. They have zero capital, execution, secret, release or risk authority.

## 8. Reporting contract

Each experiment reports: hypothesis ID; spec version; instrument/TF/session; trade count; fill rate; expectancy (R) and 95% stationary-bootstrap CI; PF and CI; max DD and ulcer index; Sharpe and HAC SE; DSR; PBO; placebo delta and CI; cost attribution; MAE/MFE; regime breakdown; sensitivity grid; gate verdict; next action.

## 9. Compliance and open owner inputs

Before automation, verify Deriv product/jurisdiction terms, applicable Kenyan requirements and any other relevant jurisdiction, and current SEBI/NSE requirements before Indian-market automation. Do not assume the user's account jurisdiction from location metadata.

Open inputs, one at a time:
1. Actual owner-approved ATOS layer map/spec.
2. Approved capital and risk numbers.
3. Instrument priority between XAUUSD and EURUSD.
4. Exact MSNR rules.
5. Deriv account product type and jurisdiction.
6. Whether Indian options automation is intended or research-only.

## 10. Evidence references

The owner-supplied reference list includes Lopez de Prado (2018), Bailey & Lopez de Prado (2014), Bailey et al. (2015), Harvey & Liu (2015), White (2000), Hansen (2005), Politis-Romano (1994), Lo (2002), Howard (2021), Ramdas (2023), Roll (1984), Corwin-Schultz (2012), Cont-Kukanov-Stoikov (2014), Hamilton (1989), Corsi (2009), Torrence-Compo (1998), Mann-Lees (1996), Kelly (1956), MacLean-Thorp-Ziemba (2010), Rockafellar-Uryasev (2000), and Federal Reserve SR 11-7 (2011). Verify exact bibliographic details and relevance before using them as evidence; a citation list is not proof that a strategy works.
