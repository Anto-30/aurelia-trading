# SYSTEM_DIRECTIVE.md
# AURELIA / ATOS v2.0 Unified Research and Execution-Control Directive

Version: 2026-10-25
Authority: safety and evidence policy for repository work
Status: FAIL-CLOSED; all release gates remain binding

## 1. Immutable controls

The following state is mandatory unless an independent human release approver changes the canonical lock in a separate, explicitly approved release change:

- LIVE_EXECUTION=BLOCKED
- FINAL_EXECUTION_AUTHORIZATION=false
- capital_plane_mode=VERIFY_ONLY
- research_capital_authority=false
- external code execution defaults to DENY_BY_DEFAULT

Do not modify config/LIVE_LOCK.yaml, grant capital authority, place/cancel/modify an order, or promote a strategy because CI passes. No model, agent, research process, or repository can bypass the human approval gate on main. Do not generate or execute authenticated real-account sessions, OTPs, or real-money trades as part of empirical validation. Public market-data requests are permitted without credentials. Any later protected, read-only broker verification requires separate human authorization and the repository's protected environment gate; it is not performed by this workflow.

## 2. Separation of concerns

- External repository intake PR #211 is limited to inventory, provenance, defensive CI and intake governance. It does not authorize live trading.
- Empirical data capture and research tooling belong in separate research changes and artifacts.
- Never vendor or execute unreviewed repositories, skills, prompts, plugins or proxy services in a capital/execution path.
- No candidate is approved without a verifiable license, source/dependency audit, isolated tests and explicit independent human sign-off.
- Repositories lacking licensing evidence, archived/deprecated sources and high-risk session/proxy tooling remain BLOCKED or excluded from adoption.

The current intake inventory contains 29 candidates: nine BLOCKED and 20 UNREVIEWED. These are review dispositions, not approved runtime dependencies.

## 3. Deriv New API rules

Public historical data endpoint:
wss://api.derivws.com/trading/v1/options/ws/public

Documented public endpoint reference:
https://developers.deriv.com/docs/options/ws-public/

Historical API reference:
https://developers.deriv.com/docs/data/ticks-history/

- Public historical probing must not use credentials, account OTPs, or authenticated endpoints.
- For candles use ticks_history, style=candles and granularity=60. The live probe in GitHub Actions run 40203287647 confirmed that the current endpoint rejects subscribe=0 with InputValidationFailed (subscribe must be 1). Since subscribe is optional and value 1 requests a subscription, omit the field for one-time historical requests. Require epoch, open, high, low and close on every returned candle.
- The published ticks_history schema constrains granularity to documented values (including 60 seconds); do not assume an arbitrary integer is accepted.
- Treat any API error, schema mismatch, timeout, missing required candle field, unexpected response, pagination stall or continuity gap as BLOCKED. Preserve the raw responses and diagnostics; never label partial data VERIFIED.
- Requested data window: 2022-10-21 00:00:00 UTC through 2024-10-21 00:00:00 UTC; epochs 1666310400 through 1729468800; one-minute candles. Both bounds are included in the strict continuity set.
- Capture raw request/response JSONL, deterministic CSV, a manifest and SHA-256 hashes. The data manifest may say VERIFIED only after every expected epoch exists exactly once after deduplication and conflicting duplicates have been rejected.
- A failed local DNS probe is an environment/network blocker, not proof of API unavailability. A secret-free public probe may be run in isolated CI. Full download is conditional on that probe passing.

## 4. MT5 reconciliation and cost calibration

MT5 reconciliation is blocked until an actual MT5 export is supplied. Never fabricate or infer mt5_bars.csv.

- Require precisely 1,440 one-minute MT5 rows, no duplicate epochs, no missing/extra timestamps in the selected 24-hour window, and exact numeric OHLC equality (tolerance 0.0) against the verified API CSV.
- Require the API file hash to match its VERIFIED manifest. The two-year API CSV must be windowed to the MT5 timestamps before comparison; do not compare the entire two-year dataset to a 24-hour file.
- If any timestamp or OHLC differs, mark reconciliation FAILED and reject MT5 as a ground-truth substitute for that window.
- Populate config/COST_MODEL.json only from genuine Deriv statement or profit_table records supplied through an approved, read-only evidence source. Do not assume spreads, commissions, fees, slippage or cash flows. Compute gross-to-net delta from the actual matched transactions, document provenance and use a strict residual tolerance.

## 5. Frozen baseline and kill rule

Do not run tools/frozen_run.py until dataset provenance, strict continuity, MT5 decision and cost calibration gates are explicitly resolved. Once authorized, run the frozen baseline exactly once against the frozen verified inputs. Record commit, data hashes, config hashes and run hash. Do not tune parameters after looking at the out-of-sample result.

Predeclared kill rule:
- Profit Factor < 1.15 OR
- Net Expectancy <= 0.0

If either is true, record FAIL, halt this strategy and do not optimize it to rescue the result. Any new strategy is a new research protocol with a new sealed out-of-sample set.

## 6. The nine empirical/operational gates

Every gate needs timestamped, source-bound evidence and SHA-256 hashes. Missing evidence means NOT_READY, not a pass.

1. Broker lifecycle: document the authorized, read-only lifecycle only when separately approved; otherwise mark BLOCKED. Do not generate live OTPs in this research task.
2. Recovery matrix: simulate public WebSocket disconnects and rate limits; prove reconnect, request correlation, state recovery and no duplicate state transitions. No trade placement is needed or allowed.
3. 3,600-second soak: run a continuous non-production public WebSocket listener for one hour; record connection continuity, memory and state-integrity metrics. Do not use live-account authentication or orders.
4. Prospective out-of-sample: use a sealed/frozen strategy and a verified, withheld dataset; record all dataset provenance and model outputs.
5. Calibration: record a pre-run configuration hash and prove parameters were not changed after the out-of-sample run.
6. Execution economics: reconcile theoretical gross PnL and observed net cash flows from genuine source statements; assumed costs are prohibited.
7. Security audit: check for hardcoded tokens/OTPs, unsafe secret access, log leakage, untrusted code execution and prompt-injection paths. CI output must be sanitized.
8. Deployment: inspect infrastructure-as-code and prove demo/real environment separation, no public secret exposure and no unapproved production deployment.
9. Strategy eligibility: apply the predeclared kill rule exactly. Failure requires a written rejection and stop.

## 7. CI/CD tiers

Tier 1 — secret-free PR CI: syntax, lint/static analysis, unit tests, dependency review, build checks and public no-auth data probes. Use read-only repository permissions. Do not attach the production environment or secrets to untrusted pull-request code.

Tier 2 — protected verification: read-only checks only, separated from Tier 1, on a protected branch and behind manual environment approval with least-privilege, short-lived credentials if separately authorized. No order submission or real-money action. CI success does not authorize live execution.

## 8. Certification and final authorization

Do not create a passing AURELIA_CERTIFICATION_REPORT.json while any gate is absent or blocked. The eventual report must contain all nine gate statuses, artifact paths, SHA-256 hashes, timestamps, code/data/config versions, failure reasons, reviewer identity and signature evidence. Include the approved dependency list and intake merge reference.

The report and evidence package must be submitted to an independent human reviewer. Only a separate, explicit human signature and release review can authorize a future change to config/LIVE_LOCK.yaml. An AI agent must never make that authorization change. Until then, maintain LIVE_EXECUTION=BLOCKED, FINAL_EXECUTION_AUTHORIZATION=false and capital_plane_mode=VERIFY_ONLY.

## 9. Evidence integrity

Do not invent API replies, candle counts, reconciliation outcomes, costs, backtest metrics, successful tests or hashes. Distinguish facts, assumptions and missing evidence. Preserve failure logs; do not silently retry away evidence of failures. Never overwrite an existing raw capture or manifest without an explicit new run ID and a distinct output path.
