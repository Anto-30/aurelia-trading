# AURELIA Empirical Gate Status — 2026-10-25

## One-page reviewer summary

**Disposition: NOT_READY / FAIL-CLOSED.** No live execution is authorized. This report records current evidence and blockers only; it is not a certification pass.

### Immutable controls

- LIVE_EXECUTION: BLOCKED
- FINAL_EXECUTION_AUTHORIZATION: false
- capital_plane_mode: VERIFY_ONLY
- research_capital_authority: false

The canonical config/LIVE_LOCK.yaml is unchanged. Public market-data tests do not use credentials. No authenticated real-account OTP or order was generated as part of this research task.

### Data prerequisite status

| Item | Current evidence | Status |
|---|---|---|
| Local tooling | Python 3.13.5; websockets 16.0; pandas 2.2.3 imports succeeded | PASS |
| Bounded R_100 historical probe | The local WebSocket attempt stopped at DNS resolution with gaierror: Temporary failure in name resolution; no request reached Deriv and no API response was observed | BLOCKED in local environment |
| Remote public probe and conditional capture | Secret-free GitHub Actions workflow is being added; its actual run output/artifact must be reviewed before any data is called verified | PENDING |
| Verified dataset | No verified CSV, raw JSONL or verification manifest has been produced by this environment | NOT READY |
| MT5 export | mt5_bars.csv was not found in the current workspace | WAITING FOR ACTUAL UPLOAD |
| Observed cost evidence | No verified transaction statement/profit_table data was supplied in this task | BLOCKED |

Official API references: https://developers.deriv.com/docs/options/ws-public/ and https://developers.deriv.com/docs/data/ticks-history/. The documented ticks_history granularity schema lists allowed values including 60 seconds; it must not be described as accepting every arbitrary integer.

### Nine release gates

| Gate | Required evidence | Current status |
|---|---|---|
| 1. Broker lifecycle | Separately authorized read-only lifecycle evidence, auth failure visibility, source/time/hash lineage | BLOCKED — this task does not generate a live-account OTP or authenticated real session |
| 2. Recovery matrix | Forced disconnect/rate-limit test logs, reconnect and state-reconciliation assertions, duplicate-state proof | NOT RUN |
| 3. 3,600-second soak | Continuous non-production public listener, 60-minute timeline, memory/connection metrics, state-integrity result and hashes | NOT RUN |
| 4. Prospective OOS | Verified data hash, frozen strategy/config hash, sealed test window, reproducible ledger | BLOCKED — data prerequisite absent |
| 5. Calibration | Pre-run parameter/config hash and immutable evidence showing no post-OOS tuning | BLOCKED — no OOS run exists |
| 6. Execution economics | Observed Deriv statements/profit_table, matched cash flows, gross-to-net reconciliation and strict residual tolerance | BLOCKED — source cash flows absent |
| 7. Security audit | Repository-wide secret scan, log sanitization proof, SAST/dependency reports and human findings disposition | PARTIAL — intake workflow/security boundaries reviewed; full source audit remains outstanding |
| 8. Deployment | IaC review proving demo/real isolation, protected environment scope and no unapproved deployment | PARTIAL — PR #211 proposes PR-safe/protected verification separation and is not merged |
| 9. Strategy eligibility | Frozen-baseline ledger; Profit Factor and net expectancy; predeclared kill-rule verdict | BLOCKED — not evaluated without verified data and cost evidence |

### Decision rules

- A probe failure, API schema mismatch, pagination stall, missing candle or continuity gap must produce BLOCKED; no verified CSV may be emitted.
- MT5 equivalence requires exactly 1,440 one-minute rows for the selected window, zero missing/extra timestamps, no duplicates and exact Decimal OHLC equality (tolerance 0.0).
- No cost model values may be assumed. They must be derived from source-bound cash flows.
- Once prerequisites are genuinely satisfied, execute the frozen baseline only once. If Profit Factor < 1.15 OR net expectancy <= 0.0, reject that strategy and halt; do not tune to rescue it.
- Do not publish a passing AURELIA_CERTIFICATION_REPORT.json until all nine gates are backed by complete evidence and an independent human reviewer signs off.

### Artifacts and provenance

The local probe produced no API output and therefore no data hash. Hashes must be computed only from actual captured files. GitHub Actions capture artifacts, if generated, are point-in-time evidence and must be downloaded, hashed/checked and retained with the associated workflow run ID and commit SHA. The current intake PR remains independent from empirical readiness and cannot authorize live execution.
