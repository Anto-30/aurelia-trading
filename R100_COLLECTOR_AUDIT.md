# R100 Collector Audit — PR #253

**Audit date:** 2026-11-05  
**Reviewed repository:** `Anto-30/aurelia-trading`  
**Reviewed collector baseline:** `998b703f4de8922b2090eb18693a40624527a790`  
**Scope:** `research/r100_prospective_oos_collector.py`, its tests, `runtime/adapters/deriv_ws.py`, and `.github/workflows/r100-prospective-oos.yml`.

This is a source audit, not a certification of strategy performance or live execution.

## Findings

| Control | Result | Evidence / limitation |
|---|---|---|
| Unique batch ID | FAIL | No batch model or `batch_id` exists. The collector creates an experiment ID and individual signal IDs only. |
| Raw response hash | FAIL | No raw WebSocket frame or API response hash is stored. `archive_hash` hashes the manifest, derived observations and proposal-quote observations; it is not a raw-response hash. |
| Fetch timestamp per batch | FAIL | The state has run-start/run-completion timestamps and per-signal/quote timestamps, but no per-batch `fetched_at_utc`. |
| Provenance alongside dataset | PARTIAL | State records strategy commit/config identity and report records strategy/collector commits and source hash. The artifact contains derived JSON state/report, not a separately hashed raw tick dataset. |
| Monotonic tick-time validation | FAIL | `epoch` is parsed and converted to UTC, but no persisted last-epoch comparison rejects older events. |
| Duplicate tick detection | NOT IMPLEMENTED | No event-level deduplication key is persisted. Do not infer duplicate-free data from WebSocket ordering. |
| Gap/continuity measurement | NOT IMPLEMENTED | No tick-gap counters, missing-interval report, or continuity threshold is applied. |
| Bounded reconnection | PASS (code + tests) | Retryable reader errors are typed; collector reconnects/resubscribes with capped exponential backoff and records reconnect events. |
| Input quote validation | FAIL (fix in progress) | Float conversion does not reject NaN, infinity, zero or negative quote values before the signal engine/state update. |
| Persistent storage format | PARTIAL | State/report are JSON and uploaded as a GitHub Actions artifact; no Parquet/Arrow writer exists. Artifact retention in this workflow is 30 days, not an indefinite data store. |
| Deriv authentication isolation | PASS (source scope) | Collector uses the documented `/trading/v1/options/ws/public` endpoint and does not import the authenticated Deriv account adapter or read Deriv credential variables. |
| Capital/execution authority | PASS (source scope) | Collector emits only research/proposal data and explicitly reports `strategy_live_eligible=false`, `execution_authorized=false`, `capital_authority=false`, and `live_execution=false`. |

## Existing verification evidence

GitHub Actions Assurance run **41477157422** on PR #253's baseline completed successfully. Its steps included:

- research-plane tests;
- assurance and runtime tests;
- secret-presence and hardening tests;
- Deriv WebSocket transport tests;
- frozen R100 strategy-source integrity;
- clean runtime container build;
- public Deriv market-data transport verification;
- readiness and fail-closed release-gate checks.

Authenticated Deriv session, broker-account and transaction-lifecycle steps were skipped. This run therefore proves neither credential validity nor account access.

The existing PR description records a previous prospective campaign with **613 OOS observations** and quoted net return per stake of **-1.0685%**, plus incomplete probability calibration. That historical campaign is negative/incomplete evidence, not a qualifying strategy.

## Explicit scope gaps

The following paths named in the proposed audit script are **not present on PR #253's audited head**:

- `research/data/deriv_tick_ingestor.py`
- `research/data/validation_pipeline.py`
- `research/data/pipeline.py`
- `tests/test_research_security_boundary.py`
- `tests/test_research_regression.py`
- `R100_COLLECTOR_AUDIT.md` (this report is being added now)
- `.github/workflows/secret-scan.yml`
- `runtime/oauth/pkce.py`
- `runtime/adapters/deriv_oauth_extension.py`

Consequently, the proposed test commands cannot be reported as previously executed. The security-boundary and regression test files have now been added to this PR branch and are being verified by its Actions workflow. The regression test is intentionally expected to expose the quote/timestamp validation gap before the fix is applied.

## Storage decision

The current collector is a signal/quote research campaign recorder, not a lossless market-tick archive. It must not be described as providing raw-batch provenance, full tick continuity, deduplication, or Parquet storage until those are implemented and tested. A later raw-data layer should preserve raw frame bytes or their hashes, event-time and receive-time metadata, batch manifests, and explicit gap/duplicate semantics.

## Safety

No broker credential was used. No authenticated account action or live order was performed. This audit does not change `LIVE_EXECUTION=BLOCKED` or `FINAL_EXECUTION_AUTHORIZATION=false`.
