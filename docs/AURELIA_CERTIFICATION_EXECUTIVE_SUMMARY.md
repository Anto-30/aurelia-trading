# AURELIA Certification — Executive Summary

**Decision: NOT_READY / BLOCKED.** This is a source-backed evidence status report, not release authorization. Evidence was refreshed on 2026-10-26; the assessed `main` commit remains `d04564aca0648201feff0326fe9af0fbcee92e94`.

## Immutable safety state

`config/LIVE_LOCK.yaml` remains at main-branch Git blob SHA `b2cddd1efb0f25f35a6a08354290f805812bf34c`:

- `LIVE_EXECUTION: BLOCKED`
- `FINAL_EXECUTION_AUTHORIZATION: false`
- `capital_plane_mode: VERIFY_ONLY`
- `research_capital_authority: false`

No candidate adoption or real-money activity is authorized by these reports. Automated CI cannot sign certification or unlock capital.

## Nine-gate decision

| Gate | Current status | Evidence / reason |
|---|---|---|
| 1. Broker lifecycle and authentication | **PENDING** | No accepted source-bound non-production lifecycle evidence package; no OTP or authenticated session was created by this review. |
| 2. Recovery, rate limits and reconciliation | **PENDING** | The localhost-only synthetic recovery matrix passed 9/9 tests, but it does not certify broker session renewal, server state reconciliation or duplicate-order behavior. |
| 3. Continuous public-feed soak | **PASS — public feed only** | [Run 40312272639](https://github.com/Anto-30/aurelia-trading/actions/runs/40312272639): 3,600.032 seconds, 1,801 ticks, 1,920 messages, 119/119 application pings, zero disconnect/protocol failures, peak RSS 31.2148 MiB and RSS growth 6,713,344 bytes. Event-log SHA-256: `753b46e1820dfa8ae10377f2424c5f6705af7a675db1a2fe9a16e6d937b560fb`. This is not authenticated broker certification. |
| 4. Prospective out-of-sample evaluation | **FAIL / BLOCKED** | Main OOS run [40369364513](https://github.com/Anto-30/aurelia-trading/actions/runs/40369364513) failed twice with `TRANSPORT_READER_FAILED`, preserving zero observations. PR [#219](https://github.com/Anto-30/aurelia-trading/pull/219) adds bounded reconnect handling; its targeted regression and Assurance passed, but an end-to-end collection and a sealed OOS ledger have not been proven. |
| 5. Parameter freeze and calibration integrity | **PENDING** | No verified OOS run with sealed configuration and post-run immutability proof. |
| 6. Execution economics | **PENDING** | No source-bound Deriv `statement`/`profit_table` cash-flow export or validated theoretical-gross versus realized-net reconciliation. No cost-calibrated PF or net expectancy is available. |
| 7. Security and dependency audit | **FAIL / coverage-limited** | Latest completed 24-repository audit [40376366859](https://github.com/Anto-30/aurelia-trading/actions/runs/40376366859) reports partial Semgrep coverage on 23/24 candidates and produces material findings. Details below. |
| 8. Deployment isolation and protected approvals | **PENDING** | The production-environment/Tier-1 workflow separation is proposed on PR [#216](https://github.com/Anto-30/aurelia-trading/pull/216) and carried into PR [#228](https://github.com/Anto-30/aurelia-trading/pull/228), but `main` requires independent review and merge before it is remediated. |
| 9. Strategy eligibility and kill rule | **PENDING — not evaluated** | Verified historical data, observed cash-flow economics and a valid sealed OOS ledger are missing. PF < 1.15 or net expectancy <= 0 remains a hard rejection rule; no baseline pass is claimed. |

## Latest external-candidate security/dependency audit

Run [40376366859](https://github.com/Anto-30/aurelia-trading/actions/runs/40376366859) completed on PR #213 head `4f096a53c1b811cc782ea1c725c2e4e102d0515a`. The run **failed closed by policy** because coverage was partial; it did not fail due to a missing report or a runner outage.

- 24 exact-pinned candidates processed; 1 Semgrep scan complete, 23 coverage-limited, 0 candidate scans blocked.
- Semgrep: 3,447 finding instances and 765 scanner-error records (716 partial parsing, 18 internal matching, 13 syntax, 11 other-syntax, 6 timeout, 1 lexical). Severity totals: 671 ERROR, 2,575 WARNING, 178 INFO and 23 MEDIUM.
- Trivy: 10,811 finding instances — 1,409 vulnerability, 63 misconfiguration, 7 secret-detection and 9,332 license instances. Severity totals across Trivy finding types: 87 CRITICAL, 696 HIGH, 609 MEDIUM, 9,191 LOW and 228 UNKNOWN. Findings require deduplication/contextual triage; these are not all confirmed exploitable vulnerabilities, and license detections are not security vulnerabilities.
- Artifact [12677757644](https://github.com/Anto-30/aurelia-trading/actions/runs/40376366859/artifacts/12677757644) ZIP SHA-256: `34af64b7db8d169418902285b9604e4fd16cd47ac14fd6bc640e140ef8edd00a`. Summary SHA-256: `c175a6407099439cec740d2782de677542f7f6ddc94dbe37f80a239ac490356b`. Source manifest SHA-256: `6f15f2095f811e06672516293c2f290fc85f2e4320b830efd8bed8e19b545692`. All 98 manifest entries were recomputed against their file bytes; all JSON artifacts parsed strictly.
- `mz-automation/libiec61850` contains four JARs that the scanner could not inspect because the Trivy Java-index database fetch failed (`TRIVY_JAVA_DB_FETCH_FAILED`). Those paths are explicitly recorded as skipped/partial; the finding counts are not a complete Java archive audit.
- No candidate code, tests or builds were executed, and no candidate dependencies were installed. The current audit manifest is a 24-candidate subset of the 81-candidate intake registry. The other 57 intake candidates do not have source-level scan coverage from this workflow. Across the intake registry, 56 candidates are BLOCKED and 25 remain UNREVIEWED; all remain unapproved.

The audit exit code of 2 is intentional: partial coverage must not pass the security gate. Remediate scanner coverage and the Java DB fetch failure, then rerun; independently triage findings before any dependency promotion. Gate 7 remains failed.

## Historical data and cost-model blockers

The required R_100 history window is 2022-10-21 00:00:00 UTC through 2024-10-21 00:00:00 UTC. The API probe returned 2026-dated candles outside the request bounds, so strict validation rejected them. No verified historical CSV, raw JSONL or provenance manifest is claimed. MT5 reconciliation has not run because the 1,440-candle export is missing. Official Deriv documentation defines `subscribe` on `ticks_history` as optional and lists only value `1`; it should be omitted for a one-time request, not set to an undocumented zero. See the [official Ticks History schema](https://developers.deriv.com/docs/data/ticks-history/) and [comparison](https://developers.deriv.com/comparison/ticks-history/).

No source-bound Deriv cash-flow export is available; costs must not be inferred or filled with synthetic assumptions. Do not execute the frozen baseline until provenance, MT5 reconciliation (if required), and observed cost-model gates are satisfied. No PF/net-expectancy verdict is available.

## Schema and Assurance

The canonical Draft 2020-12 certification schema and its config mirror have path-specific `$id` values and are tested for structural equality after normalizing those IDs. The latest report update was schema-validated by [Certification Report Schema Gate 40381898902](https://github.com/Anto-30/aurelia-trading/actions/runs/40381898902) on PR #215 head `04e29de67b0525d4288335ecff228f5cf277acf7`. The same head's AURELIA Assurance run [40381889150](https://github.com/Anto-30/aurelia-trading/actions/runs/40381889150) was still in progress at report refresh; its result must be checked before claiming exact-head Assurance passed.

PR [#228](https://github.com/Anto-30/aurelia-trading/pull/228) now has a secret-free Tier 1 Assurance workflow and the Deriv proposal/price-contract fix. Exact-head Assurance passed at [40381103451](https://github.com/Anto-30/aurelia-trading/actions/runs/40381103451) on commit `629971cbb2dd590ebf3b2711e11d2c684378dadb`. Both PRs remain unmerged and require independent human review. The workflow on `main` still requires this separation to be reviewed and merged before production workflow exposure is remediated.

## Required decisions before any release

1. Produce bounds-verified R_100 history and the required timestamp/continuity/hash manifest; supply the MT5 1,440-candle export if reconciliation remains mandatory.
2. Finish scanner coverage, investigate the Java DB fetch failure, and disposition all security/license findings; keep every external candidate unapproved meanwhile.
3. Supply observed Deriv statement/profit-table cash flows and reconcile realized net PnL before calculating expectancy or PF.
4. Obtain and independently review all nine gates, including deployment isolation and authenticated non-production lifecycle evidence, with an authorized human signature.
5. Keep `config/LIVE_LOCK.yaml` unchanged until a human release authority explicitly approves after every gate passes.

**No live execution authorization is granted. Certification remains NOT_READY.**
