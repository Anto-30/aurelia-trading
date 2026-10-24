# ATOS v2.0 / AURELIA — System Directive

**Status: RESEARCH ONLY / VERIFY_ONLY.** This file defines repository policy and validation gates; it is not a system prompt, runtime credential, execution authorization, or proof that external agent runtimes are installed.

## 1. Immutable safety state

- Preserve `config/LIVE_LOCK.yaml`; do not modify it to satisfy a workflow or make a test pass.
- Required state: `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`.
- No authenticated live broker sessions, OTP generation, real-money orders, or order-capable simulations as part of research validation.
- Never log, commit, or expose PATs, OTPs, account tokens, passwords, or production secrets.
- Missing, stale, ambiguous, or contradictory state means **BLOCKED / ABORT**, not a default or guessed value.
- CI success, code compilation, unit tests, model output, or a registered agent name is not release authorization.

## 2. Current Deriv API integration policy

All changes must be checked against the current official Deriv New API reference and captured public response schema at the time of the change. Do not copy legacy assumptions without proof.

- Research history acquisition uses only the unauthenticated public endpoint `wss://api.derivws.com/trading/v1/options/ws/public`.
- No PAT, OAuth, OTP, account, balance, statement, proposal, buy, sell, cancellation, or other authenticated operation is permitted in the public research fetcher.
- Account context is bound by the supported New API authentication/session mechanism; do not add legacy `loginid` fields to payloads unless the current official schema explicitly requires them.
- Use `underlying_symbol` where the current schema requires it; do not globally rename the operation key `ticks_history` or assume all request objects share the same field names.
- Validate prices, epochs, message types, required fields, and response ranges explicitly. A documented success-response guarantee does not justify removing defensive checks that enforce fail-closed behavior.
- One-time history requests must not subscribe unless the current schema explicitly requires it. Validate all OHLC candle fields (`epoch`, `open`, `high`, `low`, `close`) and reject missing or malformed fields.
- Do not assume an undocumented maximum history range, old-history availability, payout, spread, slippage, commission, or execution latency. Capture the actual response and error safely.

## 3. Empirical MSNR data gates

Required target window: **2022-10-21 00:00:00 UTC through 2024-10-21 00:00:00 UTC** as explicitly defined by the frozen manifest's inclusive/exclusive boundaries.

1. **Historical provenance.** Fetch only source-returned R_100 bars. Use bounded chunks, strict epoch-by-epoch continuity, duplicate/extra/missing-bar rejection, raw JSONL and final CSV SHA-256 manifests. Preserve source request/response metadata and UTC boundaries. Never interpolate, backfill, forward-fill, or substitute current candles.
2. **Fail closed on range mismatch.** A response containing candles outside the requested interval is a failed probe even if the WebSocket connection succeeds or the response contains structurally valid candles. Stop the full download until a bounded probe proves the endpoint returns the requested historical epochs.
3. **MT5 reconciliation.** Wait for a user-provided `mt5_bars.csv` export. Require the agreed matching 24-hour UTC window, exactly 1,440 matched one-minute timestamps, zero missing/extra timestamps, and exact OHLC equality (tolerance 0.0). If it diverges, reject MT5 as a ground-truth source and document the discrepancy; do not silently relax tolerance.
4. **Observed cost calibration.** Populate `config/COST_MODEL.json` only from verified cash flows in Deriv `statement` or `profit_table` data that the user separately authorizes and provides through a safe process. Derive gross-to-net differences from observed records. No assumed spread, slippage, commission, payout, or multiplier may be labelled observed. Do not collect account data in the public history fetcher.
5. **Contract economics.** Confirm the exact `contract_type` and payoff mechanics from source evidence before modelling them. If the contract type or multiplier is unknown, the cost model is not calibrated and the strategy is not eligible for evaluation.
6. **Frozen baseline.** Execute `tools/frozen_run.py` exactly once only after source, continuity, cost, and contract gates pass. Do not tune parameters after observing the evaluation result.
7. **Kill rule.** If Profit Factor < 1.15 OR net expectancy <= 0.0, document the failure and stop the strategy. Do not rescue it by changing parameters or the data window. If required inputs are unavailable, mark the kill rule **NOT EVALUATED**, not passed or failed.

## 4. Operational release gates

Before any release review, produce timestamped, commit-bound evidence for:
- verified historical CSV, raw-source evidence, manifests, hashes, and independent continuity report;
- matching MT5 reconciliation report, or documented rejection of MT5 as ground truth;
- source-observed cost model and contract type/payoff evidence;
- frozen baseline run, trade ledger, PF, net expectancy, drawdown, and kill-rule verdict;
- untouched out-of-sample evaluation and calibrated execution economics;
- continuous 3,600-second non-production soak with memory, reconnect, state-integrity, latency and recovery telemetry;
- current CI and branch-protection evidence on exact commit heads;
- independent human review of PR #159, #188, and all relevant security-sensitive changes.

An absent artifact is a failed gate. An in-progress, canceled, skipped, or environment-blocked workflow is not a pass. Prior success on a different commit does not certify the current head.

## 5. Agent, skill, and plugin policy

- Use only tools, skills, plugins, and external agents that are actually available, connected, authenticated, and relevant to the task.
- Registry membership is not proof of installation or runtime availability. Record the provider/runtime identity, successful capability probe, scope, timestamp, and attributable result before claiming delegation.
- DeepSeek Harness, Claude/OpenClaw, Fable, Kimi, Qwen, Hermes, Firecrawl, Playwright, Browser Use and other tools are advisory/development capabilities only when their connection and runtime are verified. Do not invent execution or review results.
- External agents cannot authorize capital, access production secrets, change the live lock, or submit orders.
- Keep untrusted third-party repositories in isolated development/sandbox environments; review licenses, dependencies, permissions, and code before any reuse.
- Use task-scoped least privilege rather than invoking every connector indiscriminately.

## 6. Required reporting format

For every validation cycle, report:
1. exact repository, branch, commit SHA and UTC timestamp;
2. concrete defect and affected files;
3. patch and regression tests;
4. actual commands, exit codes, and test/CI links;
5. security-boundary review and any external review identity;
6. evidence artifacts and hashes, or the exact reason they are unavailable;
7. each gate as `PASS`, `FAIL`, `BLOCKED`, or `NOT EVALUATED`;
8. the next concrete action and its owner.

Never state “complete” while any release gate is missing or unverified.

## 7. Initial recorded blocker — 2026-10-25

A bounded unauthenticated probe was executed in a disposable remote Python environment against the current public endpoint. The environment had Python 3.13.17, pandas 2.2.3, and websockets 16.1.1 after installing the missing websocket dependency for this probe. This is **not** evidence about the user's local machine.

Request: R_100, 60-second candles, start epoch 1666310400 (2022-10-21 00:00:00 UTC), inclusive end epoch 1666396740, no `subscribe`, no authentication.

Observed: WebSocket connected; response type was `candles`; 1,000 candle objects contained the five required fields, but their epochs were 1792816620 through 1792876560 (2026), outside the requested 2022 interval. The response echoed the requested start/end. The bounded probe therefore **FAILED the historical-range gate**.

Disposition: **BLOCKED**. Do not run the full 24-month download, MT5 reconciliation, frozen simulator, cost-calibrated ledger, or kill rule until a supported historical retrieval path is proven. No 24-month dataset, empirical PF/expectancy, or strategy verdict is established by this probe. The next required inputs are a supported source for the requested 2022–2024 R_100 history, the user's `mt5_bars.csv` for reconciliation, and the exact frozen strategy contract type. No authenticated session or live order was used.


## Follow-up bounded probe — 2026-10-24T21:29:15Z

A second schema-conformant one-candle probe was recorded at `reports/research/R100_HISTORY_PROBE_2026-10-25.json`. Request: `ticks_history=R_100`, `start=1666310400`, `end="1666310460"`, `style="candles"`, `granularity=60`, `count=1`; `subscribe` omitted. The response echoed the request bounds but returned epoch `1792877340` (`2026-10-24T21:29:00Z`), outside the requested half-open 2022 interval. Raw response SHA-256: `a96b9db34389de496d725d958215b7c0a7acfa9d135d67b952358291c0296a90`. Verdict remains **BLOCKED**.

Official schema correction: the current Deriv [ticks_history reference](https://developers.deriv.com/docs/data/ticks-history/) permits `subscribe=1` only; a one-shot request must omit `subscribe`, not send `subscribe=0`. This probe did not authenticate, request account data, or submit orders. It is not a historical dataset and does not justify a strategy verdict.


## Latest bounded probe — 2026-10-24T21:40:42Z

Evidence artifact: `reports/research/R100_HISTORY_PROBE_2026-10-25T2140Z.json` (raw response SHA-256 `a44382da137e88de97b5bad9915c707746ce374dad8f0cafda885073066eecd1`).

The one-candle request again echoed the 2022-10-21 00:00–00:01 UTC bounds, but the single returned candle had epoch `1792878000` (`2026-10-24T21:40:00Z`). All required OHLC/epoch fields were present; the range check failed. This is a second new, independent response showing that transport connectivity and structural schema validity do not prove requested historical coverage. Status remains **BLOCKED**. No full download, MT5 reconciliation, observed cost model, frozen simulation, or kill-rule evaluation was run.
