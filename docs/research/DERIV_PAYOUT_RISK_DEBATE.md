# Deriv payout math and bounded risk debate (research only)

## Scope and authority

This is a pure, deterministic research utility. It contains no WebSocket client, credentials, broker adapter, or order-submission path. APPROVE_RESEARCH_ONLY means only that this mathematical fixture passed its configured research checks; it is not a trading authorization. AURELIA's capital plane, broker-derived balance verification, LIVE_LOCK, release evidence, and human approval remain the only route to production execution.

## Contract cashflows

For a Deriv proposal, ask_price is the purchase cost and payout is the gross amount returned if the contract wins. Do not treat payout as the amount to pay. The net winning P&L is payout_total minus ask_price; the losing P&L is negative ask_price. An additional_cost is assumed to be external to the quote and is charged to either outcome. Never subtract a cost already reflected in the quote.

EV = p × (P − S − c) + (1 − p) × (−S − c) = p × P − S − c.

Here S is ask_price, P is payout_total, p is win probability, and c is additional unquoted cost. Break-even is (S + c) / P. Net odds for Kelly sizing are (P − S − c) / (S + c). When c=0, break-even reduces to S/P and Kelly fraction is p − (1 − p)/net_odds.

The provided example with a $10 cost, $18.50 total payout, and 55% win probability has EV $0.175 per contract, or 1.75% of the $10 risk budget. It is positive in raw expectation but fails the stricter 2% EV-buffer rule. A 50% win rate at an 85% net profit rate gives -7.5% of stake in expectation.

A larger offered payout does not, by itself, prove that the empirical chance of success is lower. Contract terms and quote construction differ; estimate probability from appropriate out-of-sample evidence and calibration, then compare it with the quote's break-even probability. Do not train the model on the assumption that payout percentage is a monotonic proxy for true win probability.

## Gate logic

The Proposer and Critic must produce independently calibrated probabilities within AURELIA's hard inclusive 0.55–0.75 band. The Critic evaluates the minimum of both probabilities and the supplied lower confidence bound. No clipping is allowed. The decision is rejected for uncalibrated inputs, probability disagreement above 10 percentage points, volatility at/above the configured 95th percentile, stale quotes or account observations, a payout drop over 1%, invalid/stale account state, daily drawdown at/above 3%, three consecutive losses, negative/insufficient EV, or a risk budget below the broker minimum. The default per-trade risk cap is 1% of equity, matching AURELIA's existing policy.

The 50 ms quote/debate age rules are guardrails, not a claim that any network path can meet that latency. Use monotonic timestamps around local events and verify p50/p95/p99 latency empirically. If a smaller stake is selected by Kelly or the hard risk cap, the current proposal must not be reused: obtain a new proposal for that stake and repeat all checks because payout terms can change.

A post-buy response is too late to undo a purchase. If later execution evidence shows an unexpected price or payout, record a violation, reconcile broker state, and halt subsequent entries under existing production controls; do not claim the trade was aborted retroactively.

## RL reward design

Use observed realized contract P&L normalized by equity as the primary outcome reward. Keep expected value as a pre-trade hard gate and record forecast calibration separately. Rewarding the model directly from its own predicted probability risks teaching overconfidence rather than realized predictive skill. Add drawdown penalties only as an explicitly measured auxiliary term while preserving raw P&L, turnover, and drawdown metrics. RL is optional, not a prerequisite: a calibrated supervised probability model plus deterministic EV/risk gates may be a simpler baseline and must be compared with RL under the same leakage-safe walk-forward protocol.

## API and reconciliation cautions

Deriv documents portfolio as the account endpoint listing open positions; proposal_open_contract reports contract status and can stream updates. Avoid polling proposal_open_contract with the undocumented contract_type="all" parameter plus a short time-window aggregation heuristic. Keep reconciliation on the existing authenticated AURELIA adapter and fail closed on incomplete responses.

Request a proposal, evaluate ask_price and payout, and—only if the separate production gate later authorizes a purchase—use ask_price as the maximum purchase price, not the gross payout. This module deliberately performs no API calls. Do not use a legacy WebSocket example to bypass AURELIA's current modern endpoint or account-binding controls.

## Validation

Run the following from the repository root:
python -m unittest research.labs.tests.test_deriv_payout_risk -v

The tests include hand-calculated EV, hard caps, circuit breakers, stale/unstable quote checks, probability policy, realized-reward behavior, and 10,000 seeded randomized cases verifying that scenarios at/below break-even never pass the research gate. Passing these tests demonstrates code properties only—not a trading edge, probability calibration, broker behavior, API latency, or production readiness.
