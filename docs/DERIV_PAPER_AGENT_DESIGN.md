# Deriv BRAIN/REFLEX/GATE: Paper Decision Core

Status: research-only implementation proposal on a feature branch. This module is not deployed and does not submit broker orders.

## Boundary

The canonical Deriv adapter remains in runtime/adapters/deriv_adapter.py; the existing deterministic capital plane, authorization context, execution firewall, ledger/reconciliation, and config/LIVE_LOCK.yaml remain the only path toward live execution. This new package is under research/paper_agent/ and has no broker client, no network calls, no order API, and no capital authority.

- BRAIN: research processes may produce only the closed Jev JSON schema; LLM output is never run per tick.
- REFLEX: validates the schema and deterministic paper risk policy; invalid or unknown inputs fail closed.
- GATE: kill-switch reset requires an operator approval reference, restored API health, cleared crisis, and recovered confidence.
- GATE: strategy deployment, material parameter changes, and any live activation still require the existing release process and human approval.
- Evidence: the SQLite ledger is append-only at the SQL layer, idempotent by event ID, and hash-chained. It records decisions, paper intents and missed signals.

## Numeric policy resolution

The proposed position_size_pct is in percentage points (for example 1.0 means 1%), not a fraction such as 0.01. AURELIA currently uses 1% planned risk as the default and 2% as an absolute ceiling. The new research gate blocks any candidate above 1.0 percentage point by default and does not introduce a configuration override. Confidence values are valid probabilities in [0, 1], and AURELIA's existing strategy policy rejects values above 0.75 rather than clipping them. The proposed 0.70 minimum is applied before a candidate can be considered.

The daily loss limit is 5% of day-start equity and the maximum drawdown limit is 15% from the high-water mark. Either limit latches the kill switch; a human approval cannot override the same breached hard limit. API errors, crisis regime, or confidence below 0.50 also latch the switch. Ordinary confidence below 0.70 blocks a signal but does not automatically latch the switch.

## What is deliberately not claimed

This commit does not claim to identify a profitable strategy, make up bid/ask data for Deriv synthetic indices, treat tick quotes as order-book imbalance, simulate a fill, or report PnL without a verified contract specification and payout/settlement source. Deriv tick streams are treated as single quotes. Spread, slippage, proposal price, payout, multiplier stop-out mechanics, and contract settlement must be sourced from actual instrument/API observations before a contract simulator can be qualified.

No market-data stream has been connected and no 30-day paper trial has been started from this branch. Tests in assurance/test_deriv_paper_agent.py are deterministic unit tests, not market evidence.

## Verification commands

    python -m unittest assurance.test_deriv_paper_agent -v
    python -m unittest discover -s assurance -p 'test_*.py' -v

## Acceptance before further integration

1. CI passes the new regression tests and existing assurance suite.
2. An independent reviewer approves the branch.
3. A separate adapter translates actual BRAIN candidates into this closed schema without passing secrets or untrusted prompt text.
4. A paper contract lifecycle uses actual Deriv instrument/proposal mechanics and records entry quotes, costs, settlement, and outcomes without submitting orders.
5. Historical validation includes time-ordered walk-forward and untouched out-of-sample windows, regime breakdowns, and realistic costs, followed by at least 30 calendar days of continuously evidenced paper operation.
6. Any later live release remains a separate human-authorized release event. This package cannot authorize it.
