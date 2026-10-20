# External Repository Audit — Validation Status (2026-10-17)

## Executive status

**Snapshot note (2026-10-17):** this document began as a 12-repository audit snapshot and its older CI section below is historical, not the current PR state. The later batch of 67 unique repositories plus the separate Odysseus assessment is recorded in [the batch review](EXTERNAL_REPOSITORY_BATCH_REVIEW_2026-10-17.md), [the portfolio triage](EXTERNAL_REPOSITORY_PORTFOLIO_TRIAGE_2026-10-17.md), and [the Odysseus assessment](ODYSSEUS_EXTERNAL_REPOSITORY_ASSESSMENT_2026-10-17.md). Current registry count is 367 (173 sandbox-only, 58 toolchain-only, 64 research-only, 72 reference-only). All remain intake classifications, not security approvals.

**Outcome: source/API review expanded; third-party integration not approved.** The companion [pinned source review](EXTERNAL_REPOSITORY_SOURCE_REVIEW_2026-10-17.md) now records exact default-branch HEAD SHAs and GitHub license metadata for all 12 unique repositories, plus direct inspection notes for selected manifests, security policies, installer code, and tool implementations. The repositories have not been cloned or executed in an isolated sandbox. This report distinguishes completed source/API inspection from the isolated source/dependency audit still required. No third-party code or dependency was added to AURELIA.

## Historical AURELIA CI snapshot from the earlier 12-repository review

At that historical snapshot, PR #155 head commit was `dd926db17372b4846f1f9fc98214a3e054753871`.

- AURELIA Assurance workflow run 39036673314 completed with workflow conclusion `success` at that historical PR head. Its job-level checks passed, but the certification gate deliberately emitted `CERTIFICATION_RESULT=NOT_READY`, `FINAL_EXECUTION_AUTHORIZATION=FALSE`, and `LIVE_EXECUTION=BLOCKED` because required production evidence is absent. Authentication-dependent Deriv session/account/lifecycle steps were skipped because `DERIV_AUTH_CONFIGURED=false`.
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

## Latest PR branch activity

- Source review document commit: `8e1abbf95e8c03ac4d49009805600c7a47b31c42`.
- The previous documentation commit `6ec79ddba25802c9f2dd7d00015ea79bd884f1e8` had successful Continuity Watchdog and Federation Audit runs. Assurance runs 39036828586 and 39036822738 were still in progress when last checked; these results are not assumed to cover the subsequent source-review commit.
- The new source-review commit triggers another set of PR checks. Recheck the latest runs for the final branch head before treating CI status as settled.

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
- [Pinned external repository source review](EXTERNAL_REPOSITORY_SOURCE_REVIEW_2026-10-17.md)
- [AURELIA Assurance run on current PR head](https://github.com/Anto-30/aurelia-trading/actions/runs/39036673314)
- [Push-triggered assurance run (status must be rechecked)](https://github.com/Anto-30/aurelia-trading/actions/runs/39036669874)
- [Agent Continuity Watchdog run on current PR head](https://github.com/Anto-30/aurelia-trading/actions/runs/39036673310)
- [Agent Federation Audit run on current PR head](https://github.com/Anto-30/aurelia-trading/actions/runs/39036673340)
- [Earlier AURELIA Assurance run](https://github.com/Anto-30/aurelia-trading/actions/runs/39036491498)
- [technicalindicators package manifest](https://github.com/anandanand84/technicalindicators/blob/master/package.json)
- [pi package manifest](https://github.com/earendil-works/pi/blob/main/package.json)
- [XERJ README/security note](https://github.com/xerj-org/xerj)


## Second full recheck — 2026-10-17

The refreshed report is [`EXTERNAL_REPOSITORY_RECHECK_2026-10-17.md`](EXTERNAL_REPOSITORY_RECHECK_2026-10-17.md). All 12 current default-branch HEADs, repository license metadata, selected security/manifests/source files, and recent workflow runs were rechecked.

Material findings:
- XERJ's current `engine/Cargo.lock` has the same blob SHA as the lockfile at upstream CI commit `6982638c336b6104121049879d6916b64c4aff15`, whose `cargo audit` job failed with six vulnerability findings. This includes `zip 8.6.0` / RUSTSEC-2026-0369 (critical 9.1) and `zip 7.2.0` / RUSTSEC-2026-0367 (high 7.3) plus RUSTSEC-2026-0368. Treat XERJ as blocked for deployment/integration until the dependency set is remediated and the audit passes.
- SIE's current security policy says its default single-server mode binds `0.0.0.0:8080` without authentication. Do not expose it with defaults; any trial needs loopback binding and token auth.
- CopilotKit/OpenBot's current desktop CI failed at `cargo fmt --check`; the log shows a formatting-only diff in `desktop/src-tauri/src/harness.rs`. Its publish and `zizmor` workflows succeeded on the current HEAD.
- Pi's security policy explicitly states it is not sandboxed. Its latest successful CI result queried was on a PR commit, not the current default-branch HEAD.
- Nightly OpenBot remains a development preview with `danger-full-access` / `approvalPolicy: never` and a non-commercial license. Its recent CI result with `action_required` was on a PR commit, not current main.
- The Claude plugin catalog's scheduled SHA-bump job succeeded on current HEAD, while plugin validation/scan failures observed were on external PR commits, not current main.
- AURELIA Assurance push run [39037173027](https://github.com/Anto-30/aurelia-trading/actions/runs/39037173027) completed successfully at prior branch head `aa38764213700211689b8135d8d6bb75a357cc88`. This means the workflow's checks passed; its certification gate still explicitly returned `CERTIFICATION_RESULT=NOT_READY`, `FINAL_EXECUTION_AUTHORIZATION=FALSE`, and `LIVE_EXECUTION=BLOCKED`. Deriv authentication remained unconfigured, and the broker lifecycle, recovery, soak, prospective OOS, calibration, execution economics, security, deployment, and strategy eligibility artifacts remained missing.
- New recheck report commit: `b3ba5b8431686d388072f003d588805a5a653748`. Current PR-head Assurance and other checks must be rechecked after this commit; results from earlier heads are not evidence for the new head.

The second recheck does not change the disposition: no third-party integration is approved, no source was executed in this session, and AURELIA's live release remains blocked until genuine evidence and independent human approval exist.
