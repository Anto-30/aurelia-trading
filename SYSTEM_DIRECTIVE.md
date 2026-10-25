# ATOS v2.0 / AURELIA Empirical & Execution Directive

**Status:** Fail-closed. This file records repository operating policy; it does not replace CI enforcement, protected branch rules, independent review, or external provider controls.

## 1. Immutable safety state

- Preserve `config/LIVE_LOCK.yaml`; never modify it to make tests pass.
- Required state: `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`, and `live_trading_enabled=false`.
- No authenticated live broker sessions, OTP generation, real-money orders, or production trading during research validation.
- Missing, stale, conflicting, or unverifiable data means `BLOCKED`; do not infer values or fabricate API responses, costs, hashes, test results, or performance metrics.
- Keep tokens, PATs, OAuth credentials, OTPs, account IDs, and other secrets out of source, logs, commits, prompts, and evidence artifacts.

## 2. Deriv New API compatibility

- Use the public market-data endpoint for unauthenticated research: `wss://api.derivws.com/trading/v1/options/ws/public`.
- Keep public research code unable to authenticate, read account state, or submit trading actions.
- Do not include legacy `loginid` in request payloads. Use `underlying_symbol` for trading/market-data request schemas where the New API requires it; retain `ticks_history` as the history request key.
- Validate the current schema at the API boundary. Candle `granularity` must be one of the documented enum values: 60, 120, 180, 300, 600, 900, 1800, 3600, 7200, 14400, 28800, or 86400 seconds.
- For `ticks_history`, `subscribe` is optional and, if supplied, the documented allowed value is integer `1` only. One-shot research requests should omit it. Do not send `subscribe: 0`: the live public endpoint returned `InputValidationFailed` / `subscribe: must be 1` during the 2026-10-25 probe. Recheck the official schema and endpoint before changing this rule.
- Validate all five candle fields: `epoch`, `open`, `high`, `low`, and `close`; enforce numeric types, finite positive OHLC, OHLC invariants, epoch alignment, strict ordering, no duplicates, and exact requested-window coverage.
- Official schema reference: https://developers.deriv.com/docs/data/ticks-history/

## 3. Empirical validation gates

Do not evaluate the MSNR kill rule until every preceding gate passes.

### Gate 1 — Historical provenance
- Required window: `2022-10-21 00:00:00 UTC` through `2024-10-21 00:00:00 UTC`.
- Fetch only after a bounded probe proves the API returns epochs inside the requested interval.
- Use bounded chunks, strict epoch-by-epoch continuity, schema validation, and SHA-256 manifests for raw responses and final normalized data.
- A response that echoes the requested bounds but returns out-of-window candles is invalid. Do not silently substitute recent data.

### Gate 2 — MT5 reconciliation
- Require the user-provided `mt5_bars.csv` for a matching 24-hour window.
- Require exactly 1,440 matched one-minute candles, no missing/extra timestamps, and exact OHLC equality with tolerance `0.0`.
- Reject MT5 as ground truth if it diverges; document the discrepancies.

### Gate 3 — Observed execution economics
- Populate `config/COST_MODEL.json` only from observed Deriv `statement` or `profit_table` cash flows, obtained through an explicitly authorized non-production research procedure.
- Compute theoretical gross PnL versus realized net PnL, record exact fee totals and a justified residual tolerance, and reject uncalibrated or unexplained residuals.
- Never assume spreads, slippage, commissions, multipliers, payouts, or linear payoff mechanics. Confirm the exact `contract_type` used by the frozen strategy.

### Gate 4 — Frozen baseline and kill rule
- Run `tools/frozen_run.py` exactly once against the verified, frozen dataset. Do not tune parameters after viewing the result.
- Kill the strategy if Profit Factor is below 1.15 **or** net expectancy is less than or equal to zero.
- Record the result and stop. Do not attempt to rescue a failed strategy by retuning on the same data.

## 4. Operational and release gates

- Run a continuous 3,600-second non-production soak with memory, WebSocket lifecycle, disconnect/reconnect, state-integrity, latency, and recovery telemetry.
- Submit data hashes, raw response evidence, MT5 discrepancy report, observed-cost proof, frozen ledger, kill-rule verdict, and soak logs for independent human review.
- Require protected branch policy, current exact-head CI, Agent Federation Audit, security review, and independent approval for PRs #159, #188, and related security-sensitive changes.
- A workflow waiting at or failing before a protected environment gate is not a test pass. Do not remove required reviewers or bypass branch protection to force success.
- Keep provider runtimes (DeepSeek Harness, Claude Code/OpenClaw, Fable, Kimi, Qwen, Playwright, Browser Use, and others) marked unverified until each has an authenticated capability probe, permission scope, timestamp, and attributable execution evidence. Registry entries are not proof of a connected runtime.
- External agents have no capital authority and may not read production secrets, mutate the live lock, or submit orders.

## 5. Required operating loop

For each subsystem, repeat: inspect the exact branch/commit; identify a concrete defect; patch an isolated branch; add regression tests; run targeted and full relevant tests; verify exact-head CI; review security boundaries; document evidence and unresolved gates. Fix failures and repeat while evidence supports further safe work.

Stop empirical progression immediately when a required gate fails. Report the exact request, response/error, timestamps, hashes, commit SHA, test output, and next missing input. Do not declare the system release-ready while any gate remains unresolved.

## 6. Current known blocker (2026-10-25)

A bounded public probe requested `R_100` candles for `[1666310400,1666310460)` UTC (2022-10-21 00:00–00:01). The endpoint accepted the request when `subscribe` was omitted but returned 1,000 candles with epochs `1792876320`–`1792936260`, outside the requested 2022 window. Raw response SHA-256: `620ebfb8b377014b39adb578d4c36409b88d00aa99fff1946597cc815c1bc43a`. Therefore historical provenance is **BLOCKED** and bulk download, MT5 reconciliation, cost calibration, frozen baseline, kill-rule evaluation, and release authorization must not proceed until a supported data source returns the exact interval.

The repository’s live lock remains the source of truth for execution state. This directive does not authorize any release or override protected controls.
