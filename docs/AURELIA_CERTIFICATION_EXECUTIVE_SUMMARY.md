# AURELIA Certification — Executive Summary

**Decision: BLOCKED.** This is an evidence-status report, not a release authorization.

## Current safety state

`config/LIVE_LOCK.yaml` on assessed main commit `d04564aca0648201feff0326fe9af0fbcee92e94` still sets `LIVE_EXECUTION: BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION: false`, `capital_plane_mode: VERIFY_ONLY`, and `research_capital_authority: false`. The file was not modified.

## Evidence outcome

- **Historical data:** blocked. The bounded R_100 history probe returned candles outside the requested 2022–2024 period; strict validation rejected them. No verified two-year CSV, raw JSONL or verification manifest is claimed. MT5 reconciliation has not run because `mt5_bars.csv` is absent.
- **Prospective OOS:** failed to collect. GitHub Actions run [40216274444](https://github.com/Anto-30/aurelia-trading/actions/runs/40216274444) retried twice and ended with `TRANSPORT_READER_FAILED`; zero observations were preserved. No performance result exists.
- **Execution economics:** blocked. There is no source-bound Deriv statement/profit_table cash-flow export to calibrate fees, payout, slippage or realized net PnL.
- **Strategy eligibility:** not evaluated. PF and net expectancy cannot be reported without verified data and actual economics. The predeclared kill rule remains PF < 1.15 OR net expectancy <= 0.
- **Security audit:** incomplete. The previous 20-candidate run failed in the scanner invocation stage for all candidates. A corrected run [40217946001](https://github.com/Anto-30/aurelia-trading/actions/runs/40217946001) was queued at report generation; its results are not yet available. No external repository is approved.
- **Operational gates:** no completed evidence package was found for the authenticated non-production lifecycle, recovery matrix, 3,600-second soak, or Demo/Real IaC separation.
- **Licensing:** `composio-community/awesome-codex-skills` and `cline/prompts` remain excluded because no top-level license file was found during the repository inspection.

## Required decisions

1. Resolve the historical API behavior and produce a hash-verified dataset before any OOS run.
2. Finish and disposition the isolated source-level scan; keep all external candidates unapproved until independent review.
3. Supply MT5 export and source-bound Deriv cash-flow records if those gates are to be evaluated.
4. Run the recovery/soak and infrastructure review only in approved non-production, secret-scoped conditions.
5. Have the independent human reviewer sign the complete evidence package. Do not unlock live execution based on CI success or this report.

**No real-money actions were performed. No live authorization is granted.**
