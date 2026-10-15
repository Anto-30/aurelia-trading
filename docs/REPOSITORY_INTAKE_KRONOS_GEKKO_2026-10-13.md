# Repository Intake: Gekko Strategies and Kronos Variants
Date: 2026-10-13
Status: Research intake only; no runtime integration or live-trading authorization.

## Decision summary

Keep AURELIA as the single canonical system. Treat the repositories below as external research references, not independently trusted agents, capital authorities, or deployable strategy packages. Do not copy entire repositories into the runtime or add their dependencies to production before isolated review.

| Repository | What it is | Proposed disposition | Main constraints |
|---|---|---|---|
| https://github.com/xFFFFF/Gekko-Strategies | Collection of legacy Gekko JavaScript crypto strategies and historical backtest results | Research-only strategy corpus; selectively port ideas to AURELIA's existing strategy interface after provenance review | README explicitly warns results are backtests, not live trading. Gekko-specific APIs/configuration and crypto-exchange assumptions are not Deriv-compatible. No license was returned in repository metadata; do not redistribute/port source until licensing is clarified. |
| https://github.com/shiyu-coder/Kronos | Financial-candlestick foundation model and tokenizer, with fine-tuning/inference examples | Primary Kronos model research candidate; build a separate offline evaluation adapter around the existing AURELIA research plane | MIT license reported by GitHub API. Model weights, model-card terms, dependencies, inference cost/latency, input schema, data leakage, calibration and out-of-sample performance still require separate review. Forecasts are features, not execution instructions. |
| https://github.com/47thtechcorner/RayCodes_Kronos | Small Indian-market advisor using Kronos-base, Ollama/Llama 3.2, yfinance and report templates | Reference implementation only; reuse concepts, not its application as AURELIA's runtime | Repository metadata reports no license. NSE/yfinance and local Ollama assumptions do not match Deriv synthetic/financial contracts. README's proof-test claims must be independently reproduced; no reported performance is accepted as qualification evidence. |
| https://github.com/raydez/kronos-ai | A-share stock prediction web app with FastAPI backend and React/TypeScript frontend, using Kronos models | Optional UI/API reference for a research-only forecast service; do not deploy as a second trading engine | Repository metadata/license needs verification. China A-share data providers, market calendars, symbol conventions and frontend/backend stack differ from AURELIA. Review API security, model downloads, data licensing and dependency health before any reuse. |
| https://github.com/rubrikinc/kronos | Go distributed monotonic-time synchronization service | Operational infrastructure reference only; consider only if AURELIA demonstrates a real distributed-clock requirement | Not a trading model. Adds a distributed service and quorum/operations burden; it does not replace broker timestamps, exchange event times, or local monotonic timers without an explicit design and failure analysis. MIT license reported by GitHub API. |

## Architecture and ownership

- Preserve one canonical repository, capital plane, release authority and evidence lineage in AURELIA.
- Claude Code is the implementation operator; ChatGPT is the architecture/review counterpart. Grok and JEV may research or challenge findings only through documented inputs/outputs. None of these agents or imported repositories receives broker credentials, order-routing authority, or permission to change release gates.
- Place all model inference, Gekko strategy translation, parameter search and replay/backtesting in the research plane. Results must be versioned and reproducible before they can be considered for promotion.
- Integrate through existing AURELIA interfaces only. Do not create a parallel engine, direct broker path, second risk manager, or alternate release authority.
- Do not treat a model forecast, backtest, community result, README claim, or AI explanation as calibrated trade probability or proof of positive expectancy.

## Required validation before any promotion

1. Record immutable source URL, commit SHA, license, dependency lock, model/weight identifiers, data source and checksums.
2. Run isolated dependency, secret, static-analysis and license checks; inspect install scripts and model-loading/download behavior before execution.
3. Define a narrow adapter contract for OHLCV/timezone/symbol/contract metadata, missing bars, stale data, inference errors and deterministic output schema. Reject unsupported instruments rather than silently mapping them.
4. Evaluate chronologically with walk-forward and untouched out-of-sample windows; include fees, spread, slippage, payout/contract economics, latency, turnover and realistic execution constraints.
5. Report calibration, coverage, directional metrics, risk-adjusted returns, drawdown and confidence intervals against simple baselines. Prevent look-ahead, survivorship, overlapping-label and train/test contamination.
6. Compare every candidate against AURELIA's existing strategies by symbol and regime. Require independent review and repeatable test evidence before registry promotion.
7. Preserve fail-closed controls: fresh broker-derived account and contract constraints, risk warden, execution firewall, idempotency, transaction verification and reconciliation remain authoritative. Research components cannot override them.
8. Keep live trading locked until the separate broker/session/lifecycle, OOS, calibration, economics, security, soak and production-runtime qualification gates are evidenced and approved.

## Evidence limitations at intake

- Public repository metadata and README content were inspected for this intake. No source code was executed, no dependencies were installed, no model weights were downloaded, no backtest was reproduced, and no runtime integration was performed.
- GitHub repository metadata reports that xFFFFF/Gekko-Strategies has no license, 47thtechcorner/RayCodes_Kronos has no license, and the license for raydez/kronos-ai was not confirmed during this intake. Treat these as no-reuse/no-redistribution until verified from the repository's actual license files and applicable terms.
- This document records a proposed disposition, not proof that these repositories have been cloned, synchronized to other agents' workspaces, installed, tested, or deployed.

## Source links

- https://github.com/xFFFFF/Gekko-Strategies
- https://github.com/47thtechcorner/RayCodes_Kronos
- https://github.com/shiyu-coder/Kronos
- https://github.com/raydez/kronos-ai
- https://github.com/rubrikinc/kronos
- Existing release gate PR: https://github.com/Anto-30/aurelia-trading/pull/123
