# AURELIA Event-Driven Macro Playbook — 2026-10-05

## Purpose

AURELIA now has a deterministic research-plane event engine for political and macro catalysts. The design implements:

`EVENT → EXPECTATION → SURPRISE → TRANSMISSION → MARKET RESPONSE → VALIDATION → TRADE/NO-TRADE`

The engine is advisory. `TRADE_CANDIDATE` means a research candidate, not an executable order.

## Current 2026 context

The U.S. federal General Election is scheduled for Tuesday, November 3, 2026. Election dates and results must be sourced from authoritative election sources and timestamped; the engine deliberately does not hard-code a political forecast.

On February 20, 2026, the Supreme Court held in *Learning Resources, Inc. v. Trump* that IEEPA does not authorize the President to impose tariffs. Tariff policy is therefore modeled as a separately sourced legal/policy event rather than assuming unlimited executive tariff authority.

## Scenario engine

| Scenario | Resolution rule | Candidate research areas |
|---|---|---|
| GOP_RETENTION | House and Senate not confirmed Democratic | Traditional energy, defense, AI infrastructure, financials |
| DIVIDED_GOVERNMENT | One chamber confirmed Democratic and the other not | Healthcare, defense, non-AI technology |
| DEMOCRATIC_SWEEP | House and Senate both confirmed Democratic | Healthcare, clean energy, infrastructure |
| UNRESOLVED | Unknown/contested chamber or result dispute | No directional political trade |

Pre-result scenario priors can be generated from House/Senate probabilities under an explicit independence assumption. They are research priors only and are not calibrated joint forecasts.

## Surprise engine

Political surprise measures the absolute change in House and Senate control probabilities and scales it to 0–100. The system trades the surprise relative to prior expectations, not the election headline alone.

## Cross-asset confirmation

The engine normalizes:

- S&P 500
- Nasdaq
- small caps
- 2Y and 10Y Treasury yield changes
- USD
- gold
- oil
- credit spreads
- VIX
- crypto

The deterministic read classifies `RISK_ON`, `RISK_OFF`, `MIXED`, or `UNKNOWN`. High-surprise risk-off states produce a `HEDGE` research posture. Mixed or insufficient confirmation produces `WAIT`.

## Relative-value and sector hypotheses

The engine produces research candidates including:

- Healthcare / Broad Market
- Defense / Industrials
- Domestic Retail / Import-Heavy Retail
- Clean Energy / Traditional Energy
- Traditional Energy / Clean Energy
- AI Infrastructure / Non-AI Technology

These are hypotheses only. They require timestamped market inputs, liquidity, valuation, earnings, and execution evidence before any separate strategy can consider them.

## Company exposure graph

Company-policy exposure is represented as:

`POLICY → INDUSTRY → COMPANY → REVENUE EXPOSURE → EARNINGS DIRECTION → EVIDENCE`

Rows without an evidence ID or with invalid exposure percentages are ignored. Exposure ranking never invents a company-policy relationship.

## Earnings and flow confirmation

Political signals should be cross-checked against:

- earnings-estimate revisions
- company guidance and primary filings
- ETF/fund-flow evidence where available
- options positioning and volatility structure
- short interest/borrow where available
- price/volume and liquidity

A political headline alone is insufficient.

## Event half-life

The module assigns explicit monitoring persistence by event class. Election headlines are short-lived; confirmed results persist longer; legislation, regulation, tariff actions, sanctions and court decisions require longer monitoring. The persistence score is a monitoring control, not a return forecast.

## Hard blockers

The event engine returns `NO_TRADE` for:

- invalid or non-finite political probabilities
- stale political evidence
- stale market evidence
- unresolved or contested results

Insufficient or mixed confirmation prevents a directional candidate from being promoted.

The module never changes:

- `config/LIVE_LOCK.yaml`
- `FINAL_EXECUTION_AUTHORIZATION`
- broker authorization
- capital-plane state
- account bindings
- Risk Warden decisions
- Execution Firewall decisions
- reconciliation state

## Probability policy boundary

Political probabilities are separate from AURELIA's trade-probability gate.

The existing hard trade-probability policy remains:

`0.55 <= trade_probability <= 0.75`

There is no clipping. Values outside that range remain rejected by the existing capital authority layer. Stale, drifting, invalid, or uncalibrated model probabilities remain no-trade conditions.

## Agent routing

`config/event_driven_agent_routing.json` assigns workstreams to:

- KimiK3 and GrokBot for political, macro, sector, company, relative-value, options, and spillover research
- ClaudeCode for engineering
- GoogleAgentSkills for security
- GLM for evidence validation
- PlaywrightCLI for browser/system verification
- AURELIA for deterministic capital controls

All communication uses the existing persistent federation. External agents remain advisory/engineering only.

## Operational states

- `TRADE_CANDIDATE`: candidate hypothesis; no order authority
- `WAIT`: information or confirmation incomplete
- `HEDGE`: high surprise with risk-off confirmation
- `NO_TRADE`: hard blocker

## Required evidence before strategy adoption

This module is deterministic and tested, but it does not prove profitability. Any strategy derived from it must independently pass AURELIA's existing OOS, calibration, execution-economics, market-data, exposure, broker, reconciliation, worker, and release gates.

The current `LIVE_LOCK` remains intentionally non-live.
