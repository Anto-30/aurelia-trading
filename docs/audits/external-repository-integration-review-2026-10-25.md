# External Repository Integration Review

**Review date:** 2026-10-25  
**Target:** `Anto-30/aurelia-trading` (`main`)  
**Scope:** Initial triage of the nine externally supplied repositories.  
**Change type:** Documentation only; no runtime code, dependencies, credentials, execution configuration, or trading strategy changed.

## Executive decision

Do not bulk-import or install these repositories into AURELIA. Treat each as an external source under review. The initial classification below is a triage decision, not a completed source-code security audit, compatibility test, or profitability validation. No external code is authorized to place orders or authorize capital.

Preserve the existing fail-closed policy: `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, and capital-plane `VERIFY_ONLY` until every release gate is evidenced and independently approved. Never weaken or infer the location/content of the canonical live lock from a guessed path.

## Repository-by-repository disposition

| Repository | Triage disposition | Allowed evaluation scope | Required gates before reuse |
|---|---|---|---|
| [google/artemis](https://github.com/google/artemis) | Conditional; not a trading dependency | Android/UI automation only if a mobile QA requirement exists | Confirm upstream purpose and maintenance; isolate test devices/accounts; no production credentials; run a bounded smoke test |
| [apache/artemis](https://github.com/apache/artemis) | Conditional; defer deployment | Message-broker prototype only if measured requirements show a broker is needed | Threat model; supported protocol/auth configuration; TLS and secret handling; durability/recovery test; load/latency benchmark; operating-cost justification |
| [omnigent-ai/omnigent](https://github.com/omnigent-ai/omnigent) | Priority for source review; not approved for integration | Development-time agent orchestration and sandbox research | Inspect exact commit, license, dependencies, subprocess/network/file permissions, sandbox escape boundaries, prompt/tool injection controls, audit logs, policy enforcement, tests, and failure modes; run isolated tests |
| [ls1intum/Artemis](https://github.com/ls1intum/Artemis) | Exclude from trading runtime | Separate educational/training use only if a concrete requirement is approved | Demonstrate a direct product need and conduct separate deployment/security review |
| [Roibal/Cryptocurrency-Trading-Bots-Python-Beginner-Advance](https://github.com/Roibal/Cryptocurrency-Trading-Bots-Python-Beginner-Advance) | Research-only; no production imports | Read-only strategy study in a disposable sandbox | Pin commit; inspect exchange SDK/API age and secrets; remove any order-capable path from experiments; test fees, spread, slippage, latency, partial fills, outages, rate limits, and survivorship/lookahead bias; validate out-of-sample |
| [jrmeier/fast-trade](https://github.com/jrmeier/fast-trade) | Priority for offline backtest comparison; no dependency approved | Compare its backtest assumptions and outputs with AURELIA's frozen simulator | Verify exact commit, API and test status; audit candle alignment, lookahead, fill rules, costs, missing data, timezone handling, and reproducibility; run parity fixtures and sealed out-of-sample tests. README identifies AGPL-3.0; obtain license review before copying, linking, or distributing derivative/combined code |
| [superset-sh/superset](https://github.com/superset-sh/superset) | Optional development-workspace candidate; defer | Isolated developer worktrees only | Review exact commit, permissions, agent execution boundaries, and security posture; determine license implications. Repository `LICENSE.md` states Elastic License 2.0; obtain legal review before adoption or redistribution |
| [CERT-Polska/Artemis](https://github.com/CERT-Polska/Artemis) | Security-tool candidate; not yet approved | Scan only systems and targets for which authorization exists | Pin and inspect code/dependencies; run against a disposable local target first; document scope/rate limits and findings; prevent production scans without explicit authorization |
| [Artemis-RGB/Artemis](https://github.com/Artemis-RGB/Artemis) | Exclude | None for current AURELIA scope | Reconsider only if a documented peripheral/RGB requirement appears |

## Architectural invariants

1. Layer 6 remains the sole deterministic risk authority. A strategy, agent, broker, plugin, imported bot, or language model cannot authorize capital or bypass risk checks.
2. Keep a single canonical capital plane, execution firewall, ledger/reconciliation path, and release authority. Do not create duplicate capital managers or execution adapters as a side effect of repository reuse.
3. Imported code remains outside production runtime until pinned, reviewed, dependency-scanned, tested, and explicitly accepted. Never execute an unreviewed repository merely to discover what it does.
4. All experiments use read-only data or a synthetic/local fixture. No live credentials, live orders, or real-account access in candidate-repository tests.
5. For Deriv synthetic indices, do not assume exchange order-book depth, maker/taker fees, true volume/CVD, or portable crypto-exchange execution semantics.
6. Performance claims require reproducible, cost-adjusted walk-forward and sealed out-of-sample evidence. A repository's own sample results or benchmarks do not establish AURELIA profitability.
7. Pin source commit SHA and dependency versions; record license, provenance, test commands, raw outputs, and reviewer decisions. Do not copy third-party source before license compatibility is cleared.

## Acceptance checklist

- [ ] Capture exact upstream commit SHA, default branch, last-updated date, license file, and release/tag for each candidate.
- [ ] Inspect source and build/test manifests; produce an SBOM and dependency vulnerability scan.
- [ ] Check for secrets, unsafe subprocess/shell use, unrestricted network/file access, dynamic code execution, telemetry, and unsafe deserialization.
- [ ] Establish isolated reproducible test environments and record exact commands, exit codes, and outputs.
- [ ] For `fast-trade`, compare trade timestamps, signal timing, fills, commissions/spread/slippage, missing candles, and equity calculations against a frozen AURELIA baseline.
- [ ] For agent tooling, demonstrate deny-by-default tool permissions, sandbox boundaries, and no path from agent output to capital authorization.
- [ ] For security scanning, prove the target is owned or explicitly authorized and test against a local disposable service first.
- [ ] Obtain independent code review and license approval before any source/dependency import.
- [ ] Run required repository assurance and relevant regression tests on the proposed patch.
- [ ] Preserve live execution block and human release gates; no merge or deployment is implied by this report.

## Verified observations and limitations

- GitHub API access confirmed that `Anto-30/aurelia-trading` has a `main` branch and a repository tree containing 518 entries at the time of inspection.
- The attempted path `CONFIG/LIVE_LOCK.yaml` returned 404 on `main`. This does **not** prove that the lock is absent; the canonical path must be found from the actual repository tree before any lock-related action.
- The GitHub branch-protection endpoint returned no branch-protection data for `main`. Treat this as an unresolved governance risk until repository rulesets and branch protection are inspected; do not guess required CI check names or change protection settings blindly.
- Repository documentation was inspected for selected candidates, and repository metadata was queried. This pass did **not** clone or execute the candidates, inspect every source file, complete an SBOM/vulnerability scan, run AURELIA tests, or verify live/deployment behavior.
- Therefore this document records an initial review and safe next steps only. It is not a security certification, compatibility sign-off, or performance claim.

## Next action

Review this documentation-only change, locate the canonical live-lock path from the tree, verify repository rulesets/branch protection, then perform source-level audits of Omnigent and fast-trade in isolated environments. Do not merge until an independent reviewer and required checks approve. Do not authorize live execution as part of this work.
