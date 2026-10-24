# ATOS v2.0 / AURELIA Empirical & Execution System Directive

**Status:** Fail-closed. This document governs research and verification only; it does not grant execution authority.

## 1. Immutable safety state

- Preserve `config/LIVE_LOCK.yaml`; do not weaken, overwrite, or bypass it to make a workflow green.
- Required state: `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`.
- No real-money trades, authenticated live broker sessions, OTP generation, or live-order simulation during this workflow. Public, unauthenticated market-data probes are permitted.
- Missing, stale, contradictory, or unverifiable evidence means `BLOCKED` / `STATE UNKNOWN — ABORT`.
- Never fabricate market data, execution economics, test results, reviewer approval, or agent participation. Do not print, commit, or place tokens in logs, prompts, fixtures, artifacts, or URLs.

## 2. Deriv New API schema discipline

- Use the official Deriv New API documentation and schema for the exact endpoint being called. Do not mix legacy and New API assumptions.
- For supported requests, use `underlying_symbol` where the New API schema requires it; remove `loginid` from payloads where the New API schema has removed it. Do not mechanically rename fields on endpoints whose schemas differ.
- Validate `price >= 0` for `buy` and `sell` requests; use price `0` for market sells only where the current endpoint schema documents that behavior.
- Treat successful-response required fields according to the current schema, but retain boundary validation and explicit error handling. Never dereference a response blindly merely because a prior schema version promised a field.
- Historical candle requests must validate `epoch`, `open`, `high`, `low`, and `close`, plus symbol, timeframe, requested range, response range, monotonicity, and continuity.
- The public WebSocket endpoint is `wss://api.derivws.com/trading/v1/options/ws/public`. The verified documentation allows `subscribe` value `1` when present. A live probe returned `InputValidationFailed` / `subscribe must be 1` for `subscribe: 0`. For a one-shot history request, omit `subscribe` rather than sending `0`. This schema observation overrides the earlier draft instruction to send `subscribe: 0`.
- Official reference: https://developers.deriv.com/docs/data/ticks-history/ and https://developers.deriv.com/docs/options/ws-public/.

## 3. Historical-data provenance gate

Required R_100 window: **2022-10-21 00:00:00 UTC through 2024-10-21 00:00:00 UTC**.

1. Verify the runtime and package versions. A remote sandbox check is not proof of what is installed on the user's local computer.
2. Begin with a bounded, unauthenticated request against the documented public endpoint. Record the exact request, UTC boundaries, response, runtime, timestamp, and error.
3. Reject the dataset if returned candle epochs fall outside the requested window, if requested historical epochs are not returned, if the endpoint silently substitutes recent data, or if any schema/continuity check fails.
4. Only after the bounded probe proves that the requested historical interval is retrievable may a chunked download begin. Enforce exact epoch-by-epoch continuity, UTC normalization, deduplication rules, and stable chunk boundaries.
5. Preserve raw JSONL and normalized CSV; calculate SHA-256 hashes for both. Record request parameters, fetch times, source endpoint, code commit, package versions, and all gaps/errors in a manifest. Never claim data verification from a partial probe.

### Current empirical status

A bounded public probe for the first minute of the required window connected successfully, but the server returned candle epoch `1792867680` rather than an epoch in the requested 2022 interval. This does **not** establish historical availability. The historical provenance gate is **BLOCKED**; do not start a bulk download, fabricate a substitute dataset, or run the frozen baseline.

## 4. MT5 reconciliation gate

Wait for the user to provide `mt5_bars.csv`. Do not claim the file exists until it is actually received and inspected. For the specified 24-hour minute-bar window require exactly 1,440 unique matched minute timestamps, zero missing/extra timestamps, and exact OHLC equality with tolerance `0.0`. If reconciliation fails, report the precise discrepancies and reject MT5 as ground truth. Do not relax the tolerance to force a match.

## 5. Cost calibration and frozen baseline

- Do not populate `config/COST_MODEL.json` from guessed spreads, commissions, slippage, payout assumptions, or generic fee rates.
- Extract actual realized cash flows from authorized Deriv `statement` or `profit_table` data supplied through an approved, non-live research process. Derive gross-to-net residuals from matched trades, document inclusion/exclusion logic, and set `known_fees_total` and `residual_tolerance_total` only from those observations.
- Confirm the exact MSNR contract type and payoff model from the strategy code and user confirmation before calibrating economics. Do not infer `CALL`, `MULTDOWN`, or any other contract type.
- Run `tools/frozen_run.py` exactly once only after data, reconciliation, and cost-model gates pass. Freeze the code/config/data hashes before running; do not tune parameters after seeing results.
- Kill rule: if Profit Factor < 1.15 **or** net expectancy <= 0.0, declare the strategy dead for this specification, preserve the evidence, and halt. No parameter rescue or repeated frozen runs.

## 6. Risk engine and ML/research controls

- Layer 6 must be deterministic, isolated from strategy/model logic, and fail closed. Any timeout, state loss, invalid input, stale data, risk calculation error, or policy ambiguity rejects the trade.
- ML/DL predictions are advisory inputs only; they cannot authorize capital, bypass Layer 6, alter the live lock, or rewrite policy.
- Separate training, validation, and sealed out-of-sample data chronologically. Fit preprocessing and feature transformations on training data only. Prevent lookahead, leakage, survivorship bias, and overlapping-label leakage. Report uncertainty and cost-adjusted results.
- Track net expectancy, Profit Factor, drawdown, exposure, trade count, confidence calibration, costs, and failure modes. A high win rate alone is not evidence of edge.
- Never assume Deriv synthetic indices provide exchange order-book depth, maker/taker fees, or real exchange volume/CVD unless a source explicitly provides those data.

## 7. Soak, security, and release gates

Before any release recommendation, require all of the following as separate evidence:
- Exact-head CI and Assurance workflows pass, with protected branch rules and secret boundaries verified.
- Independent reviewer approval for security-sensitive changes; an owner-only environment reviewer is not independent approval.
- Authenticated **verify-only** broker lifecycle tests only when permitted and without live orders.
- Verified historical-data manifest and hashes, MT5 reconciliation result or documented rejection, observed cost proof, frozen ledger, and kill-rule verdict.
- A continuous 3,600-second non-production soak with timestamped telemetry for memory, WebSocket lifecycle/reconnects, errors, data freshness, and state consistency. Do not report a soak as passed unless the full duration and logs are present.
- Runtime persistence, recovery tests, incident/kill-switch verification, and explicit release authorization from the designated human authority.

A green unit test or CI run does not prove profitability, historical data validity, independent review, successful soak, or live readiness. Keep release blocked until every required gate is independently evidenced.

## 8. Repeatable repair loop

For each subsystem:
1. Inspect the current source, exact branch/commit, open issues/PRs, and failing tests.
2. Identify one concrete defect supported by code or logs.
3. Patch only on an isolated branch; do not modify the protected live lock.
4. Add regression tests that fail before the patch and pass after it.
5. Run focused tests, relevant broader tests, static/security checks, and exact-head CI.
6. Inspect failures, logs, changed files, secret exposure, permissions, and deployment gates; fix and repeat.
7. Record commit SHA, test commands/results, CI URLs/conclusions, remaining risks, and review status.
8. Leave the PR unmerged and release blocked if independent review or any release evidence is missing.

## 9. External agents and tools

Use only actually connected and callable tools. Record which agent/tool produced which output and preserve its run identifier and evidence. Do not claim that DeepSeek Harness, Claude Code, OpenClaw, Fable, Kimi, Qwen, Hermes, Playwright, Firecrawl, or any other external agent reviewed or changed code unless a verifiable execution result exists. External agents may perform research/review tasks only; they have no capital authority and cannot change the live lock or release gates.

## 10. Required missing inputs

The following are user-provided or source-derived requirements, not assumptions to fill automatically:
- `mt5_bars.csv` for the exact 24-hour reconciliation window.
- A verified local historical fetcher console log or an explicit reproducible failure. A remote-sandbox probe must be labelled as such and is not local-terminal output.
- Confirmed MSNR contract type/payoff mechanics from code and user confirmation.
- Authorized, redacted evidence of realized Deriv cash flows for cost calibration; never request the user to paste a secret token.

Until these inputs and the source-data gate are satisfied, report **BLOCKED** and do not run the frozen baseline or enable live execution.
