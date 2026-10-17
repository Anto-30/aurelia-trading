# External Repository Audit — Validation Status (2026-10-17)

## Executive status

**Outcome: triage completed; third-party integration not approved.** The 12 unique repositories have not been cloned or executed in an isolated sandbox. This status report distinguishes completed checks from items still requiring an isolated source/dependency audit. No third-party code or dependency was added to AURELIA.

## AURELIA CI runs on the documentation PR

Current PR #155 head commit: `dd926db17372b4846f1f9fc98214a3e054753871`.

- AURELIA Assurance workflow run 39036673314 completed with workflow conclusion `success` at the current PR head. Its job-level checks passed, but the certification gate deliberately emitted `CERTIFICATION_RESULT=NOT_READY`, `FINAL_EXECUTION_AUTHORIZATION=FALSE`, and `LIVE_EXECUTION=BLOCKED` because required production evidence is absent. Authentication-dependent Deriv session/account/lifecycle steps were skipped because `DERIV_AUTH_CONFIGURED=false`.
- The push-triggered assurance run 39036669874 on the same commit was still in progress at the time of this update; do not treat it as a second completed pass.
- Earlier AURELIA Assurance run 39036491498 completed with workflow conclusion `success` on prior PR head `80f3b34478b4c8bf374c67aa2e3403f9721721d7`.
- Compile, static production acceptance audit, shell syntax checks, research tests, assurance tests, runtime tests, secret-presence tests, hardening tests, container build, public Deriv market-data transport check, readiness report, worker health check, and fail-closed live release gate all completed successfully.
- The repository certification step returned its expected blocked result: `CERTIFICATION_RESULT=NOT_READY`, `FINAL_EXECUTION_AUTHORIZATION=FALSE`, `LIVE_EXECUTION=BLOCKED`.
- Authenticated Deriv real-account session, read-only broker evidence, and verify-only lifecycle steps were **skipped** because `DERIV_AUTH_CONFIGURED=false`. They were not passed.
- The certification output explicitly reported missing evidence: `evidence/broker_lifecycle.json`, `evidence/recovery_matrix.json`, `evidence/soak_3600s.json`, `evidence/prospective_oos.json`, `evidence/calibration.json`, `evidence/execution_economics.json`, `evidence/security_audit.json`, `evidence/deployment.json`, and `evidence/strategy_eligibility.json`.
- The final release-gate check confirmed `LIVE_RELEASE_GATE=BLOCKED` because `config/LIVE_LOCK.yaml` disables live trading.
- AURELIA Agent Continuity Watchdog run 39036491428 completed successfully, including inventory assignments, safety boundary, advisory-worker probe, and capital-protection assertion.

These CI results validate the existing AURELIA workflow at this PR head; they do not validate the external repositories and do not authorize live trading.

## Direct source inspection beyond README

### `anandanand84/technicalindicators`

Inspected `package.json` on the repository's default branch. It declares package version `3.1.0`, MIT license, a development stack including Babel 6, Mocha 2, Gulp 3 and TypeScript 2.9, and `@types/node` v6-era dependencies. This is a clear compatibility/maintenance warning, not proof of a vulnerability. Recommendation remains **test-only candidate**: do not add as a production dependency until the exact commit, dependency tree, license, numerical behavior, and supported runtime are independently validated. In particular, the old build toolchain should be treated as untrusted and run only in an isolated, unprivileged environment.

### `earendil-works/pi`

Inspected root `package.json` on the default branch. It is a private npm monorepo with many workspaces and scripts for dependency pinning, runtime dependency checks, import/entry-graph checks, browser smoke tests, builds and tests. The root declares Node.js `>=22.19.0`, TypeScript 7 and pinned direct development dependencies. This supports further source review, but does not prove the whole monorepo or every extension is safe. Review the exact commit, tool permissions, extension loading, network calls, and package-specific license before any adoption.

### `xerj-org/xerj`

The README describes local indexing/search and MCP integration. It explicitly states that `--insecure` disables TLS and API-key authentication, granting any reachable caller broad read/delete access to indexed content and memory. The documented safe use is local development bound to loopback; do not expose insecure mode to a network. No binary was downloaded or executed.

## What remains incomplete

1. Exact commit SHA and per-file license review for every candidate repository.
2. Source-level inspection of shell/install scripts, extension loading, authentication, filesystem boundaries, subprocess execution, outbound network access and secret handling.
3. Isolated dependency resolution, SBOM generation, vulnerability and secret scans, and malware screening.
4. Builds/tests/benchmarks for the selected candidate repositories in an isolated runner without secrets, network privileges beyond necessary package fetches, or access to AURELIA production files.
5. Golden-vector parity tests for technical indicators against AURELIA's canonical calculations.
6. Independent human review and explicit owner approval for any code integration.

These steps have not been represented as completed. The connected GitHub tool provides repository/file and workflow interfaces but does not provide a general-purpose local shell/clone session in this conversation. It would be inaccurate to claim local clones, SBOMs, dependency scans, or third-party test results without running them in a real isolated environment.

## Safety and release decision

- Do not merge external code based on this report.
- Do not install the `nightly-labs/openbot` development preview into a production or trading environment: its README describes broad shell access and a non-commercial license.
- Do not deploy either OpenBot as a privileged agent until authentication, sandboxing, filesystem scope and approval controls are independently verified.
- Keep all LLMs and agents outside the capital plane; no broker credentials, order submission, or risk override permissions.
- Keep `LIVE_EXECUTION=BLOCKED` and `FINAL_EXECUTION_AUTHORIZATION=FALSE` until genuine broker, strategy, calibration, execution-cost, soak, security and deployment evidence has been produced and independently reviewed.
- No paid resource was created; no live order or broker transaction was submitted; no credentials were read, copied or disclosed.

## Evidence links

- [PR #155](https://github.com/Anto-30/aurelia-trading/pull/155)
- [AURELIA Assurance run on current PR head](https://github.com/Anto-30/aurelia-trading/actions/runs/39036673314)
- [Push-triggered assurance run (status must be rechecked)](https://github.com/Anto-30/aurelia-trading/actions/runs/39036669874)
- [Agent Continuity Watchdog run on current PR head](https://github.com/Anto-30/aurelia-trading/actions/runs/39036673310)
- [Agent Federation Audit run on current PR head](https://github.com/Anto-30/aurelia-trading/actions/runs/39036673340)
- [Earlier AURELIA Assurance run](https://github.com/Anto-30/aurelia-trading/actions/runs/39036491498)
- [technicalindicators package manifest](https://github.com/anandanand84/technicalindicators/blob/master/package.json)
- [pi package manifest](https://github.com/earendil-works/pi/blob/main/package.json)
- [XERJ README/security note](https://github.com/xerj-org/xerj)
