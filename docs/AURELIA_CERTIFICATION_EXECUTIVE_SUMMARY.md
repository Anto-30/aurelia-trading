# AURELIA Certification — Executive Summary

**Decision: BLOCKED.** This is an evidence-status report, not a release authorization.

## Current safety state

`config/LIVE_LOCK.yaml` on assessed main commit `d04564aca0648201feff0326fe9af0fbcee92e94` still sets `LIVE_EXECUTION: BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION: false`, `capital_plane_mode: VERIFY_ONLY`, and `research_capital_authority: false`. The file was not modified.

## Evidence outcome

- **Historical data:** blocked. The bounded R_100 history probe returned candles outside the requested 2022–2024 period; strict validation rejected them. No verified two-year CSV, raw JSONL or verification manifest is claimed. MT5 reconciliation has not run because `mt5_bars.csv` is absent.
- **Prospective OOS:** failed to collect. GitHub Actions run [40216274444](https://github.com/Anto-30/aurelia-trading/actions/runs/40216274444) retried twice and ended with `TRANSPORT_READER_FAILED`; zero observations were preserved. No performance result exists.
- **Execution economics:** blocked. There is no source-bound Deriv statement/profit_table cash-flow export to calibrate fees, payout, slippage or realized net PnL.
- **Strategy eligibility:** not evaluated. PF and net expectancy cannot be reported without verified data and actual economics. The predeclared kill rule remains PF < 1.15 OR net expectancy <= 0.
- **Security audit:** incomplete and blocked pending source-scan completion and human disposition. Earlier runs [40217946001](https://github.com/Anto-30/aurelia-trading/actions/runs/40217946001) and [40218136417](https://github.com/Anto-30/aurelia-trading/actions/runs/40218136417) failed because Semgrep attempted to write `/root/.gitconfig` on a read-only container. The next run [40222995058](https://github.com/Anto-30/aurelia-trading/actions/runs/40222995058) failed a stale uniqueness assertion (20 expected vs 24 pinned); that count bug was fixed. A later retry [40223741330](https://github.com/Anto-30/aurelia-trading/actions/runs/40223741330) reached the source-scan stage but still failed the container Git config write. The current corrected run [40300773677](https://github.com/Anto-30/aurelia-trading/actions/runs/40300773677) passes scanner image pulls, writable Git-config smoke checks, harness syntax/manifest validation and the new regression tests; the 24-candidate source/dependency scan step remains IN_PROGRESS. No findings, SBOMs or clean result are confirmed yet. Intake tracks 33 candidates, 12 blocked, and none approved.
- **Recovery matrix:** partial synthetic-only pass. Run [40218683466](https://github.com/Anto-30/aurelia-trading/actions/runs/40218683466) passed 9/9 localhost fault-injection checks, with two mock connections, unique request IDs and zero trade commands. It does not prove authenticated Deriv session renewal, broker-state reconciliation or duplicate-order prevention.
- **3,600-second soak:** failed. Run [40205890054](https://github.com/Anto-30/aurelia-trading/actions/runs/40205890054) terminated after 120.463 seconds with one disconnect/protocol failure (61 ticks). Retry [40218683458](https://github.com/Anto-30/aurelia-trading/actions/runs/40218683458) was queued and had no result at report refresh.
- **Other operational gates:** no completed evidence package was found for the authenticated non-production lifecycle or Demo/Real IaC separation.
- **Licensing:** `composio-community/awesome-codex-skills` and `cline/prompts` remain excluded because no top-level license file was found during the repository inspection.

## CI diagnostics

- **Certification schema:** the checked-in report is validated against `schemas/aurelia_certification_report.schema.json`; schema-gate run [40224185642](https://github.com/Anto-30/aurelia-trading/actions/runs/40224185642) passed on the latest schema/report update available at report generation, including seven schema regression tests. This refresh changes report metadata only and preserves gate 7 as `PENDING`; schema validity is not security certification.
- **AURELIA Assurance:** latest runs on repair branches [40302075514](https://github.com/Anto-30/aurelia-trading/actions/runs/40302075514), [40302065657](https://github.com/Anto-30/aurelia-trading/actions/runs/40302065657), and rerun attempt 2 for [40301614079](https://github.com/Anto-30/aurelia-trading/actions/runs/40301614079) failed before any step was recorded. GitHub reports `runner_id=0`, empty `steps`, and the job-log endpoint returns `BlobNotFound`; this is a pre-run runner/service failure with root cause UNKNOWN, not evidence that application tests failed or passed. The failed-job retry reproduced it. PR #216 retains the separate secret-free Assurance hardening; code correctness remains UNVERIFIED by those no-step runs.

- **External repository sync:** repaired on draft PR [#218](https://github.com/Anto-30/aurelia-trading/pull/218). Run [40302075471](https://github.com/Anto-30/aurelia-trading/actions/runs/40302075471) passed policy checks, all five sync unit tests, active reachability (`296/296`) and snapshot upload. Two historic `REFERENCE_ONLY` records return public GitHub REST 404 and remain explicitly unavailable/exempt from the active denominator, with old pins retained only for provenance. Artifact [aurelia-external-repo-sync-40302075471](https://github.com/Anto-30/aurelia-trading/actions/runs/40302075471/artifacts/12640452744) uploaded; artifact ZIP SHA-256: `e079c47da5f4c77d7f9770784f50cd831bd6f085aff7cea259e47b8bc0b180c1`. This does not approve either unavailable repository.
- **R100 transport repair:** draft PR [#219](https://github.com/Anto-30/aurelia-trading/pull/219) now preserves sanitized WebSocket reader failure causes and implements bounded reconnect/resubscribe for the classified reader-drop case. Its Assurance attempts are pre-run failures (`runner_id=0`, no steps); the patch is not yet CI-verified and main OOS remains blocked. No strategy performance is inferred.

## Required decisions

1. Resolve the historical API behavior and produce a hash-verified dataset before any OOS run.
2. Finish and disposition the isolated source-level scan; keep all external candidates unapproved until independent review.
3. Supply MT5 export and source-bound Deriv cash-flow records if those gates are to be evaluated.
4. Run the recovery/soak and infrastructure review only in approved non-production, secret-scoped conditions.
5. Have the independent human reviewer sign the complete evidence package. Do not unlock live execution based on CI success or this report.

**No real-money actions were performed. No live authorization is granted.**
