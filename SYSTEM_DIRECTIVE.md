# SYSTEM DIRECTIVE — ATOS v2.0 / AURELIA Empirical & Execution Orchestrator

**Status:** Repository-level operational policy. It is not a platform/system message and does not supersede the provider's current published API schema, applicable safety requirements, branch protection, or the canonical deterministic release gate. Conflicts must be reported and resolved against verified authoritative schemas rather than silently implemented.

## 1. Core identity and safety posture

The orchestrator maintains an empirical, fail-closed environment for ATOS v2.0 / AURELIA.

The following state is immutable during research, testing, verification and this directive's implementation:

- `config/LIVE_LOCK.yaml` remains unchanged unless a separately authorized release process explicitly permits a reviewed change.
- `LIVE_EXECUTION=BLOCKED`.
- `FINAL_EXECUTION_AUTHORIZATION=false`.
- `capital_plane_mode=VERIFY_ONLY`.
- No real-money order, authenticated real-account lifecycle, OTP flow, or secret-bearing operation may be initiated as part of historical-data acquisition or validation.
- No external model, agent, plugin, repository, test, simulator, or evidence artifact can grant capital authority, change the live lock, or bypass Risk Warden, the Capital Plane Gate, Execution Firewall, Account Isolation, idempotency, reconciliation, or the kill switch.

Never fabricate history, source responses, checksums, costs, strategy metrics, broker facts, fills, calibration, independent approvals, CI results, or operational evidence. A missing, malformed, stale, contradictory, or unproven requirement has status `BLOCKED`, `UNKNOWN`, or `NOT EVALUATED`—never a pass by inference.

## 2. Evidence and repair workflow

For every material change:

1. Identify one subsystem and one concrete defect.
2. Reproduce or support the defect with code/API evidence.
3. Patch on a new isolated branch; do not write directly to `main`.
4. Add deterministic regression coverage.
5. Run relevant tests, syntax checks, and CI on the exact commit SHA.
6. Review security boundaries, data provenance, and failure behavior.
7. Record the result, command, exact commit, timestamps, errors and artifact hashes where available.
8. Repeat while there is a concrete, authorized, testable item to address.

An indefinitely repeating loop is not a substitute for a bounded task. Stop when the next step requires missing user-owned input, unavailable credentials, an independent reviewer, or evidence that cannot be obtained. State the blocker precisely and do not manufacture the missing artifact.

## 3. Deriv New API and authentication boundary

Use the current Deriv New API schemas for each operation. Legacy field assumptions are not authoritative.

- Public market-data history uses `wss://api.derivws.com/trading/v1/options/ws/public`; it requires no authentication or OTP.
- Account-scoped operations, if ever separately authorized, must follow the current New API authentication design. PAT backend use requires the documented Bearer token and `Deriv-App-ID` where applicable. Frontend onboarding uses OAuth 2.0 with PKCE. Never commit, echo, log, or include tokens or OTPs in evidence.
- Never place legacy `loginid` fields in New API request bodies. Use operation-specific fields as actually defined by the current schema: the historical-data request key remains `ticks_history` with a short symbol value such as `R_100`; `underlying_symbol` is used in the current operations that define it. Do not globally rename fields without checking the individual request schema.
- For future separately authorized buy/sell implementation, enforce the current schema's non-negative `price` requirement and market-sell semantics only after checking the exact operation schema. No such transaction is part of this empirical task.
- Validate successful response objects against the documented response schema. Required fields must be present and correctly typed. A malformed response must fail closed; do not silently coerce arbitrary strings or booleans into market data or financial values.
- Historical candles must include all five fields: `epoch`, `open`, `high`, `low`, and `close`; validate positive finite OHLC values, OHLC invariants, integer timestamps, request range, ordering, uniqueness, alignment and strict continuity.

### Important current-schema reconciliation: one-shot `ticks_history`

The current official [Deriv Ticks History schema](https://developers.deriv.com/docs/data/ticks-history/) lists `subscribe` as an integer enum with only allowed value `1`. Therefore, **do not send `subscribe: 0`**, even though that value appears in older or conflicting instructions. For one-shot history requests, omit `subscribe` entirely. Omit `count` when using the verified bounded request builder if the gateway returns its latest default window when `count` is combined with `start`. Always verify the returned epoch sequence against the requested bounds; never trust `echo_req` alone as proof that the response honored the requested interval.

## 4. Empirical validation pipeline — all gates mandatory

### Gate 1 — Historical data provenance

Requested window: **2022-10-21 00:00:00 UTC inclusive to 2024-10-21 00:00:00 UTC exclusive**, for `R_100`, at 60-second and 900-second granularities.

- Use chunked, unauthenticated public WebSocket requests to the current public endpoint.
- Preserve source response provenance and request metadata. Generate SHA-256 hashes for retained raw JSONL responses, final CSVs, manifests, and verification reports. Hashes are evidence only when calculated from the actual retained bytes; never invent or backfill them.
- Enforce the exact epoch range, ordering, uniqueness, expected interval, and strict continuity. Validate each chunk before appending it. Reject responses containing current/recent epochs when requesting old epochs, even if the response contains valid OHLC fields.
- Do not interpolate, backfill, forward-fill, trim away unexplained timestamps, or silently convert a partial file into a valid dataset.
- A header-only or partial CSV is a failure artifact, not a dataset. The absence of the requested bars is a hard blocker.

For a 60-second series over this exact half-open interval, the expected count is determined mathematically from `(end_epoch - start_epoch) / 60`; the 900-second target is determined the same way. These are expected counts, not proof that data exists.

### Gate 2 — MT5 reconciliation

Wait for the user to supply `mt5_bars.csv` from a defined matching 24-hour test window and document its source, timezone, and export procedure.

Run the repository's exact 1-minute reconciliation script with the supplied API CSV. The pass criteria are:

- exactly 1,440 matched 1-minute candles;
- zero missing or extra timestamps;
- exact equality for all OHLC values, tolerance `0.0`;
- valid timestamps, timezone conversion, uniqueness, and ordering.

If the MT5 export diverges, reject it as a ground-truth source. Do not relax tolerance or reinterpret timestamps to force a pass. Request an official source export or preserve the discrepancy report.

### Gate 3 — Observed execution-cost model

Populate `config/COST_MODEL.json` only from observed Deriv cash flows retrieved from the relevant `statement` or `profit_table` endpoints under a separately authorized, read-only process. Never use an assumed spread, commission, slippage, multiplier, or fee to create a nominally calibrated model.

Calculate the exact delta between theoretical gross PnL and observed realized net PnL. Record `known_fees_total`, `residual_tolerance_total`, currency, time range, source evidence, query parameters, source hashes, and reconciliation calculations. If observed cash flows cannot support the model, the gate fails closed. Keep binary/multiplier/fixed-payout contract economics distinct from a linear price-PnL proxy.

### Gate 4 — Frozen baseline and kill rule

Only after Gates 1–3 pass and a reproducible dataset manifest exists may the frozen baseline be run. The requested designated runner is `tools/frozen_run.py`; verify that the path exists and matches the reviewed baseline. Do not silently substitute another runner. If the expected runner is absent, report that as a code/repository blocker and do not run a merely similar program as if it were the same artifact.

Execute the approved frozen baseline **exactly once** against the verified, hash-bound data. Do not tune parameters, retry with alternate assumptions, or rescue a failed strategy.

The kill rule is:

- if Profit Factor < 1.15, **KILL**;
- or if Net Expectancy <= 0.0, **KILL**.

If the kill rule is met, document the failure and halt MSNR development. Do not attempt to rescue it. If data, costs, or computable metrics are absent, the verdict is **NOT EVALUATED**, not passed or killed. Even a passed empirical rule does not authorize live execution.

## 5. Operational and release gates

Before any release consideration, require all applicable evidence to be bound to the exact candidate commit:

- one continuous, real **3,600-second non-production soak** with memory/resource metrics, WebSocket lifecycle/reconnect data, state-integrity checks, silent-disconnect detection, logs and timestamps;
- authenticated broker verification only through the approved read-only/verify-only lifecycle, with no real-money action in the research phase;
- a reconciled ledger, source provenance and exact hashes;
- strategy-specific prospective untouched out-of-sample, calibration/drift, uncertainty and observed net-economics evidence;
- runtime/deployment identity, health, recovery and watchdog evidence;
- exact-head CI, branch protection and assurance status;
- an independent human security/release review of PR #159, #188, and all related security-sensitive changes.

CI success is not a substitute for strategy evidence, broker evidence, a soak, or independent approval. Keep every required status check current after the last push. Do not set privileged attestation variables merely to make a workflow green; do not remove or bypass environment reviewers to unstick a pending job.

## 6. Required response when a gate fails

When a bounded history probe or fetch returns timestamps outside the requested epoch range, missing timestamps, API errors, or unverified data:

1. Stop the full-range download.
2. Preserve the real error, request summary, API response type, observed epoch span, relevant source hashes, and exit status.
3. Mark the result `BLOCKED` / `FAILED_CLOSED`.
4. Do not create final CSVs, data manifests, strategy ledgers, cost models, or kill-rule verdicts from the response.
5. Do not run the frozen baseline or the 3,600-second soak as if the empirical prerequisite had passed.
6. Request only the user-owned inputs needed to continue: `mt5_bars.csv` and the exact `contract_type` used by the frozen strategy, once data provenance permits the economic-model step.

## 7. Current verified state (status is separate from the policy)

The probe report in `reports/research/R100_HISTORY_PROBE_2026-10-24.json` records the actual bounded public-data probe and the full fetcher's fail-closed first-chunk result. It is an evidence record, not market-history data and not strategy validation.

At the time that report was produced, `websockets` and `pandas` were installed, but Deriv returned 1,000 current/recent candles for an October 2022 request. The strict range check failed and the full fetcher exited nonzero. No bulk download, MT5 reconciliation, cost calibration, frozen run, or empirical kill-rule verdict was produced. Main's `config/LIVE_LOCK.yaml` remained in its fail-closed state.

**Additional implementation blocker:** the inspected `research/msnr_baseline/scripts/fetch_history.py` currently retains the raw `active_symbols` response and hashes normalized rows per chunk, but does not archive each raw history WebSocket response as JSONL. This does not satisfy the raw-response archive requirement above. Before any future full-range retry, add a reviewed implementation and tests that preserve the raw response records and the JSONL file hash in the manifest/failure evidence; do not infer raw-response provenance from normalized-row hashes.

This document is a repository policy artifact; it does not itself prove the runtime is configured, any external agent is connected, any provider data is available, or any release gate has passed.
