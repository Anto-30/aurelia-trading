# AURELIA Certification — Executive Summary

**Decision: BLOCKED.** This is an evidence-status report, not a release authorization.

## Current safety state

`config/LIVE_LOCK.yaml` on assessed main commit `d04564aca0648201feff0326fe9af0fbcee92e94` still sets `LIVE_EXECUTION: BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION: false`, `capital_plane_mode: VERIFY_ONLY`, and `research_capital_authority: false`. The file was not modified.

## Evidence outcome

- **Historical data:** blocked. The bounded R_100 history probe returned candles outside the requested 2022–2024 period; strict validation rejected them. No verified two-year CSV, raw JSONL or verification manifest is claimed. MT5 reconciliation has not run because `mt5_bars.csv` is absent.
- **Prospective OOS:** failed to collect. GitHub Actions run [40216274444](https://github.com/Anto-30/aurelia-trading/actions/runs/40216274444) retried twice and ended with `TRANSPORT_READER_FAILED`; zero observations were preserved. No performance result exists.
- **Execution economics:** blocked. There is no source-bound Deriv statement/profit_table cash-flow export to calibrate fees, payout, slippage or realized net PnL.
- **Strategy eligibility:** not evaluated. PF and net expectancy cannot be reported without verified data and actual economics. The predeclared kill rule remains PF < 1.15 OR net expectancy <= 0.
- **Security audit:** incomplete and blocked. The first 24-candidate retry [40222995058](https://github.com/Anto-30/aurelia-trading/actions/runs/40222995058) exposed a stale validator expecting 20 unique repositories even though the manifest contained 24 distinct pinned repositories. That root cause is fixed in the audit harness: candidate uniqueness is now checked against the actual manifest length, and the obsolete 20-candidate error label is corrected. Run [40223741330](https://github.com/Anto-30/aurelia-trading/actions/runs/40223741330) has passed image pulls, scanner smoke tests and syntax/manifest validation and is currently executing the source/dependency scans for 24 candidates. No scan findings, SBOM completion, or clean result are yet confirmed. Run [40223747995](https://github.com/Anto-30/aurelia-trading/actions/runs/40223747995) is queued with the additional smoke-test `HOME`/Git-config isolation fix. Intake tracks 33 candidates, 12 blocked, and none approved.
- **Recovery matrix:** partial synthetic-only pass. Run [40218683466](https://github.com/Anto-30/aurelia-trading/actions/runs/40218683466) passed 9/9 localhost fault-injection checks, with two mock connections, unique request IDs and zero trade commands. It does not prove authenticated Deriv session renewal, broker-state reconciliation or duplicate-order prevention.
- **3,600-second soak:** failed. Run [40205890054](https://github.com/Anto-30/aurelia-trading/actions/runs/40205890054) terminated after 120.463 seconds with one disconnect/protocol failure (61 ticks). Retry [40218683458](https://github.com/Anto-30/aurelia-trading/actions/runs/40218683458) was queued and had no result at report refresh.
- **Other operational gates:** no completed evidence package was found for the authenticated non-production lifecycle or Demo/Real IaC separation.
- **Licensing:** `composio-community/awesome-codex-skills` and `cline/prompts` remain excluded because no top-level license file was found during the repository inspection.

## CI diagnostics

- **Certification schema:** the checked-in report is now validated against `schemas/aurelia_certification_report.schema.json`; schema gate [40223975152](https://github.com/Anto-30/aurelia-trading/actions/runs/40223975152) passed on commit `4cfc7fd89a91b930235ca82fda5b3792c40a34e7`. The workflow now also triggers when `AURELIA_CERTIFICATION_REPORT.json` changes.
- **AURELIA Assurance:** runs [40223975154](https://github.com/Anto-30/aurelia-trading/actions/runs/40223975154) and [40223968938](https://github.com/Anto-30/aurelia-trading/actions/runs/40223968938) failed before any step was recorded. GitHub reports `runner_id=0`, empty `steps`, and the job-log endpoint returns `BlobNotFound`; this is a pre-run failure with root cause UNKNOWN, not evidence that a test failed or passed. One rerun reproduced the same no-step condition. Do not relabel this as a code fix; the separate secret-free Assurance hardening remains in PR #216.

## Required decisions

1. Resolve the historical API behavior and produce a hash-verified dataset before any OOS run.
2. Finish and disposition the isolated source-level scan; keep all external candidates unapproved until independent review.
3. Supply MT5 export and source-bound Deriv cash-flow records if those gates are to be evaluated.
4. Run the recovery/soak and infrastructure review only in approved non-production, secret-scoped conditions.
5. Have the independent human reviewer sign the complete evidence package. Do not unlock live execution based on CI success or this report.

**No real-money actions were performed. No live authorization is granted.**
