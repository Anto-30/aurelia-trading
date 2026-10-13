# AURELIA $0.35 Micro-Capital Mode — Engineering Specification

Status: **proposed; not implemented or live-authorized**  
Canonical PR: #123  
Branch: `fix/probability-broker-minimum-policy-2026-10-13`

## Objective

Support a user-requested USD 0.35 fixed stake only when the exact Deriv contract actually supports it, while making the increased account risk explicit. This mode must not alter the existing 1%-of-verified-available-balance policy or weaken any existing release gate.

## Risk disclosure

A USD 0.35 purchased-contract stake represents up to USD 0.35 contractual loss. On a USD 1.45 balance, that is approximately 24.14% of available capital. On a USD 35.00 balance, it is 1%. This mode is not described as 1%-risk sizing; it is a distinct, explicitly configured high-risk micro-capital policy.

## Required policy behavior

1. Default to disabled and verify-only. No configuration change may enable live trading.
2. Require an authenticated, independently bound real account; fresh broker-reported USD available balance; and matching currency/account identity.
3. Require a fresh Deriv proposal for the exact underlying symbol, contract type, duration/expiry, barrier (where applicable), and currency, with `basis="stake"` and `amount=0.35`. Reject broker errors, absent/invalid proposal IDs, mismatched quote parameters, stale responses, or any returned contract cost above USD 0.35.
4. A proposal is a quote, not proof that the purchase will be accepted. Before any eventual live release, verify broker-side minimums/constraints and the buy price/contract terms; do not synthesize a minimum from caller input or a hard-coded constant.
5. Require available balance to cover USD 0.35 plus any applicable fees/charges, with no credit/leverage assumptions. Do not use the remembered or UI-displayed balance as evidence.
6. Enforce one open contract at a time, no martingale, no stake escalation, no averaging down, and no blind resubmission. After one USD 0.35 loss in the configured session/day window, stop new entries and require the defined reset/reconciliation process.
7. Any timeout or partial buy response becomes `UNKNOWN`; block all new orders until statement/portfolio/open-contract reconciliation resolves it.
8. Preserve probability policy (55%–75% inclusive; never clip), calibration, freshness, drift checks, positive expected value after all costs, strategy-specific out-of-sample qualification, exposure controls, account isolation, kill switch, watchdog, security review, and independent release authority.
9. Report the mode as high-risk and show the maximum contractual loss and the percentage of verified available balance before any authorization. Reject if any required input is stale, unverified, contradictory, or missing.
10. Keep `config/LIVE_LOCK.yaml` disabled until every independent production gate passes. No CI success, proposal quote, documentation change, or simulated test alone authorizes live trading.

## Deterministic decision

Authorize only if every required gate returns a verified pass. Otherwise return a stable block reason such as `MICRO_STAKE_MODE_DISABLED`, `ACCOUNT_UNVERIFIED`, `BALANCE_STALE`, `CURRENCY_MISMATCH`, `EXACT_CONTRACT_QUOTE_MISSING`, `STAKE_UNAFFORDABLE`, `CONTRACT_COST_EXCEEDS_LIMIT`, `STRATEGY_NOT_QUALIFIED`, `UNKNOWN_TRANSACTION_REQUIRES_RECONCILIATION`, or `LIVE_RELEASE_GATE_BLOCKED`. Do not convert any unknown state into pass.

## Required tests before review

- USD 0.35 proposal request uses stake basis and the exact contract fields.
- Broker rejects $0.35 or returns a quote above $0.35 => blocked.
- Stale/missing quote, wrong currency/account/contract, or missing proposal ID => blocked.
- Balance under $1 plus applicable charges => blocked.
- $1.45 balance illustrates 24.14% stake exposure and is visibly flagged high-risk; the existing 1% policy remains unchanged.
- Existing $1.50 minimum with $0.35 requested stake => blocked, never rounded upward.
- Probability below 55% or above 75%, uncalibrated/drifted signal, negative net economics, unqualified strategy, stale balance, kill switch, or live lock => blocked.
- Duplicate/timeout/partial buy => UNKNOWN and no retry until reconciled.
- Property/adversarial tests prove no configuration or caller-supplied scalar can bypass the live lock or evidence provenance.
- Full test suite, security/dependency scans, 3,600-second soak, production runtime evidence, broker lifecycle/reconciliation, and independent human review all pass before any release decision.

## Current known implementation gap

The existing Deriv adapter can request a proposal but does not yet expose a source-bound exact-contract minimum-stake evidence object to the risk authority. The policy and adapter contract, runtime enforcement, and adversarial tests must be implemented and independently reviewed. This specification alone does not close those gaps.

## Release status

**BLOCKED.** Do not place a real order. No authenticated live account, current balance, exact-contract proposal, execution lifecycle, strategy qualification, soak, or production-host evidence is asserted by this document.
