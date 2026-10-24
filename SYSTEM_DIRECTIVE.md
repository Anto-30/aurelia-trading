# ATOS v2.0 / AURELIA Empirical & Execution Directive

**Updated:** 2026-10-24  
**Status:** FAIL-CLOSED / VERIFY_ONLY. This document defines policy; it is not proof that any provider is connected or that a release gate has passed.

## 1. Immutable safety state

The canonical config/LIVE_LOCK.yaml is authoritative. Preserve it unchanged until every applicable release gate has valid evidence tied to the exact candidate commit and the authorized release process explicitly approves a transition.

Required state:
- LIVE_EXECUTION=BLOCKED
- FINAL_EXECUTION_AUTHORIZATION=false
- capital_plane_mode=VERIFY_ONLY
- No live orders and no authenticated broker session, OTP, or real-money activity in this research workflow.
- Missing, stale, conflicting, or unverifiable evidence means BLOCKED, never a guessed fallback.
- Never put PATs, OAuth tokens, OTP URLs, production credentials, or unnecessary account identifiers in source, chat, logs, screenshots, manifests, fixtures, or PR artifacts. Rotate credentials that may have been exposed.

## 2. Deriv API schema authority

Use the current official schema for the exact endpoint and API release. Do not infer request fields from a legacy SDK, the name of another endpoint, or a repository registry.

Official references:
- Ticks History: https://developers.deriv.com/docs/data/ticks-history/
- Public Options WebSocket: https://developers.deriv.com/docs/options/ws-public/
- New API overview and OTP lifecycle: https://developers.deriv.com/docs/intro/api-overview/
- Ticks History comparison: https://developers.deriv.com/comparison/ticks-history/
- Published JSON/OpenAPI schemas: https://github.com/deriv-com/deriv-api-schemas/releases/latest/download/schemas.zip

### 2.1 Public historical market data

For the documented public ticks_history endpoint, the request field is ticks_history containing the short symbol, for example "R_100". Do not replace that field with underlying_symbol unless the schema for a different, specifically identified endpoint requires that field. Request field names are endpoint-specific.

The current official Ticks History schema documents:
- ticks_history: required string; pattern ^\w{2,30}$.
- end: required string; pattern ^(latest|[0-9]{1,10})$.
- start: optional integer from 0 through 9,999,999,999.
- style: ticks or candles.
- granularity for candles: integer enum 60, 120, 180, 300, 600, 900, 1800, 3600, 7200, 14400, 28800, 86400.
- count: explicitly set an integer within the supported bound where page size matters; do not rely on the default.
- subscribe: the documented enum permits integer 1 only. For one-shot historical requests, omit subscribe. Do not send subscribe: 0; it is not a documented value.

Use wss://api.derivws.com/trading/v1/options/ws/public for unauthenticated public market data. A public market-data connection is not an authenticated account session and does not prove trading/account readiness.

Candle responses must include epoch, open, high, low, and close. Validate JSON types, finite positive OHLC values, epoch bounds, strictly increasing timestamps, no duplicates, and OHLC invariants. Do not coerce strings or booleans into market data.

### 2.2 Account-scoped API

Account-scoped Options API calls use the documented authentication flow. Backend PAT calls require the proper Bearer authorization and Deriv-App-ID; web onboarding uses OAuth 2.0 with PKCE where applicable. An authenticated WebSocket URL is obtained through the documented OTP endpoint; the returned URL contains a single-use, short-lived credential. Never print or persist the URL/token.

Do not implement or test an authenticated lifecycle in this research task. Any future implementation must be separately authorized, reviewed, and validated in verify-only/non-production mode.

Do not include legacy loginid fields unless the exact current endpoint schema explicitly requires them. Conversely, do not apply the Options trading field name underlying_symbol to the distinct ticks_history request.

For successful responses, validate required objects and fields explicitly. Avoid redundant optional chaining where a schema guarantees presence, but do not remove validation or turn missing/malformed fields into success. Fail closed with a controlled error.

Price/order fields must follow the exact contract endpoint schema and observed contract economics. Do not infer that every buy/sell request has identical price semantics. No order may be sent in this workflow. Whether a market sell accepts price 0 requires endpoint-schema evidence and remains untested here.

## 3. Historical data provenance gate

Target interval: [2022-10-21T00:00:00Z, 2024-10-21T00:00:00Z) for R_100.

Calculated boundaries:
- Start epoch: 1666310400.
- Exclusive end epoch: 1729468800.
- Duration: 731 days.
- Expected complete minute-aligned count: 1,052,640 one-minute bars and 70,176 fifteen-minute bars. These are calculated expectations, not observed data.

Before any full download, make a bounded request. The response must demonstrably contain the requested historical boundary/period. A successful handshake, non-empty response, or recent 2026 candles do not pass this gate.

Each accepted page must be tied to its exact symbol, endpoint, UTC interval, granularity, request/response, retrieval time, and code version. Every epoch must be inside the half-open target range. Reject duplicates, missing/extra/out-of-order timestamps, gaps/overlaps, wrong page boundaries, invalid OHLC fields, and non-matching bar counts. Preserve raw JSONL and final CSV, compute SHA-256 hashes, and record row/page counts, dependencies, UTC boundaries, and validations in a manifest.

If the requested old interval is unavailable or a request for an old period returns recent candles, stop and record BLOCKED_HISTORICAL_RANGE_UNAVAILABLE or a more specific verified error. Never substitute recent data, a different broker feed, or MT5 as an unproven equivalent.

## 4. MT5 reconciliation gate

The native mt5_bars.csv export has not been evidenced in the current workspace. Do not manufacture a file or claim reconciliation.

After the user supplies the export:
- Verify the exact MT5 symbol/instrument and server, 1-minute timeframe, timestamp basis/timezone, row ordering, duplicates, and target UTC coverage.
- Compare the same symbol, granularity, and [start,end) interval against verified Deriv API data.
- Required 24-hour test: exactly 1,440 candles; zero missing/extra/duplicate timestamps; exact OHLC equality with tolerance 0.0.
- Report counts, missing/extra times, mismatches, and source hashes without exposing private identifiers.
- If any value/time differs, reject MT5 as a ground-truth substitute for that symbol/window. A mismatch does not by itself establish which feed is correct; request an authoritative source or documented provider evidence.

## 5. Cost model, frozen baseline, and kill rule

Do not populate config/COST_MODEL.json with assumed spreads, slippage, fees, multiplier values, payouts, or generic OHLC P&L. Use verified contract-specific specifications and observed cash flows from the relevant Deriv statement/profit_table endpoints. Reconcile theoretical gross P&L against realized net cash flows and document the derivation of known_fees_total, residual_tolerance_total, and the theoretical-to-realized residual.

Do not run tools/frozen_run.py until the exact script, strategy/config hashes, valid historical data, contract type, and cost model have been verified. Then execute the frozen run once; do not tune after seeing its result. If Profit Factor < 1.15 OR net expectancy <= 0.0, record KILL, archive evidence, and halt. Do not rescue or retune the strategy under the same evaluation.

Until valid cost-adjusted ledger evidence exists, Profit Factor, expectancy, drawdown, calibration, and strategy eligibility are NOT EVALUATED—not passed and not fabricated as zero.

## 6. Layer 6 risk and Layer 9 research

Layer 6 is a deterministic, independent, fail-closed risk authority. Strategy code, ML models, LLMs, and orchestration agents cannot authorize capital, bypass circuit breakers, change the live lock, or submit orders. Invalid numerics, missing state, stale data, API errors/timeouts, or failed reconciliation reject action and emit a traceable reason.

Layer 9 evidence must be reproducible from hash-bound inputs and exact commits. Prevent lookahead, temporal leakage, arbitrary threshold tuning, sample selection bias, and reuse of sealed OOS data for model selection. Use chronological train/validation/test splits and untouched final OOS; report calibration and uncertainty as well as point metrics. Do not claim strategy performance from insufficient or unverified samples.

Before repairing a Layer 6/strategy/Layer 9 issue, capture the actual strategy rules, entry/exit code, risk limits, contract type, data alignment policy, error logs, and observed failure. If one is missing, name it explicitly; do not invent production-ready behavior.

## 7. Operational and release gates

The release remains BLOCKED until independent evidence exists on the exact candidate commit for:
- Verified 2022–2024 R_100 data and hashes.
- Native MT5 export and strict reconciliation or documented rejection.
- Contract-specific economics and hash-bound net trade ledger.
- Frozen MSNR verdict and sealed walk-forward/prospective OOS evidence.
- Layer 6 risk/circuit-breaker, calibration and drift tests.
- Authenticated read-only/verify-only broker lifecycle only after separate authorization; never real orders in this workflow.
- Continuous 3,600-second non-production soak with memory, connection/reconnect, state integrity, health and recovery evidence.
- Persistent runtime identity, health, restart/deployment and source synchronization evidence.
- Protected branch rules, exact-head CI, independent security review and separate human approval.
- Evidence manifest linking each output to the exact data, configuration and code commits.

Green CI, repository policy changes, provider registry entries, a public socket connection, or code changes do not prove release readiness.

## 8. Agent and tool federation

Use only relevant installed/connected tools, and verify provider/runtime identity and permissions at execution time. A registry entry is not proof of connection. Mark unavailable integrations BLOCKED_NOT_CONNECTED. Never claim DeepSeek Harness, Claude Code/OpenClaw, Hermes, Fable, Kimi, Qwen, Playwright, or browser-agent work ran unless an attributable tool result exists. External agents are advisory-only, must not receive secrets, and cannot authorize capital or edit LIVE_LOCK.

## 9. Current probe evidence and blockers

A bounded public WebSocket probe for the 2022-10-21 start epoch connected but returned candle epochs in October 2026. The target historical epoch was absent. Therefore historical-range validation is BLOCKED, and no full download may start until a new bounded probe demonstrably reaches the requested period.

The local workspace currently lacks mt5_bars.csv. No MT5/API equivalence, cost-calibrated model, frozen MSNR verdict, authenticated broker lifecycle, or completed 3,600-second soak is established by this document.

## 10. Next actions

1. Preserve config/LIVE_LOCK.yaml and keep live execution blocked.
2. Resolve historical R_100 range availability via a documented source that supplies the target epochs; keep the failing response and hashes as evidence.
3. Obtain the user's native MT5 export for the approved matching 24-hour window, with symbol/server/timezone identified.
4. Confirm the frozen MSNR contract type and payoff semantics before calibrating costs.
5. Run exact reconciliation, then and only then run the frozen baseline once under the kill rule.
6. Complete independent security/operational review and the 3,600-second soak before any release decision.

**Final invariant:** If data, economics, API schema, authentication boundary, or release evidence is uncertain, stop and report the exact verified blocker. Never invent data, hashes, console output, model reviews, broker activity, performance metrics, or authorization.
