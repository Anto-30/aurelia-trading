# AURELIA External Repository Intake and Agent Assignment

**Status:** Proposed intake; metadata existence checked on 2026-10-14. No upstream code has been imported, executed, or approved for production by this manifest.
**Target:** `Anto-30/aurelia-trading`
**Branch:** `research/rust-repo-intake-2026-10-14`
**Invariant:** One canonical system, one capital plane, one release authority, one evidence lineage. `LIVE_LOCK` remains enforced.

## 1. Agent roles and tool assignments

| Role / agent | Accountable work | Required tools | Required skills / checks | Explicit limits |
|---|---|---|---|---|
| ChatGPT — research coordinator | Break down work, maintain evidence ledger, compare findings, issue go/no-go recommendations | GitHub read/search/PR tools; web research; repository manifest; test/evidence artifacts | Quant research design; data leakage review; evidence provenance; release checklist | No claim of local clone/test unless recorded; no capital authority |
| Claude Code — primary implementation agent | Inspect repositories in isolated worktrees; implement adapter/prototype changes on task branches | Git; Rust stable toolchain; Cargo; rustfmt; Clippy; test runner; cargo-audit/cargo-deny where available; GitHub PR workflow | Rust engineering, dependency review, unit/integration/property tests, reproducible builds | Never edit LIVE_LOCK to permit trading; never deploy or merge unreviewed code |
| Independent reviewer / Dev AI | Review diffs and test evidence independently; challenge assumptions and edge cases | GitHub diff/PR review; test logs; dependency/license reports; static-analysis output | Adversarial code review; correctness; failure-mode analysis; security checklist | Must not rely solely on implementer's self-report |
| Grok — external research specialist (if connected) | Research project purpose, maintenance, known issues, relevant literature and alternatives | Public web/GitHub read-only; issues/releases/commit history | Source-backed technical research; claim/citation discipline | No write access or execution authority required |
| JEV — integration and operations specialist (if connected) | Map accepted components to existing AURELIA modules; check runtime/observability impact | Repository tree/search; CI logs; deployment/runtime read-only evidence | Integration contracts; monitoring; rollback; runbooks | No broker credential access; no independent live release |
| Quant research specialist | Test candidate features/portfolio/statistical methods on isolated datasets | Python/Rust test harness; versioned datasets; backtest reports; experiment tracking | Chronological splits; walk-forward/OOS; costs/slippage; calibration; multiple-testing controls | Simulations are not broker evidence; no strategy promoted from in-sample metrics alone |
| Security reviewer | Audit supply chain, build scripts, networking, unsafe code and license obligations | cargo-audit, cargo-deny, SBOM/license inventory, secret scanner, static analyzers | Threat modelling; dependency provenance; least privilege | Never run untrusted scripts with secrets or production credentials |

Agents are role assignments, not evidence that those external agents or their environments are currently connected. Only tools confirmed callable in the current session may be described as executed.

## 2. Required toolchain and quality gates

- Rust: pinned stable toolchain and `rust-toolchain.toml` where applicable; Cargo lockfiles committed for applications.
- Static quality: `cargo fmt --check`, `cargo clippy --all-targets --all-features -- -D warnings` where compatible, and `cargo test --workspace` or repository-documented equivalent.
- Supply chain: review licenses, dependency tree, build scripts, network calls, unsafe blocks, advisories, abandoned crates, and transitive dependencies. Use `cargo audit` and `cargo deny` if installed/available.
- Python candidates: isolated virtual environment/container, pinned requirements, tests, lint/type checks as available; do not install globally.
- Quantitative candidates: frozen dataset/version, deterministic seeds, train/validation/test chronology, walk-forward tests, realistic spread/commission/slippage, survivorship/look-ahead checks, drawdown and tail-risk metrics, uncertainty intervals, and untouched OOS results.
- Security: no broker secrets, tokens, personal data or production environment variables in test environments; use synthetic fixtures and least-privilege credentials.
- Evidence: record upstream URL, resolved commit SHA, retrieval timestamp, license, test commands, exit codes, artifact hashes, reviewer, known gaps and disposition.
- Integration: isolated branch + pull request; human review and passing CI required. Never merge automatically based on agent scores.

## 3. Repository intake register

Priority is an initial hypothesis, not a statement that the repository is production-ready. Exact upstream commit SHAs, license review, test status and compatibility remain **pending** until each repository is inspected and pinned.

| Repository | Initial assignment | Priority | Intake disposition / gate |
|---|---|---:|---|
| https://github.com/tradytics/eiten | Quant research | P1 | Python portfolio/backtesting reference; inspect license and data assumptions; do not treat equity portfolio methods as a validated Deriv strategy |
| https://github.com/superlinked/sie | Agent research retrieval/inference | P2 | Evaluate only if local model serving or document retrieval solves a measured need; capacity and operational costs required |
| https://github.com/rust-lang/rust | Rust toolchain reference | P2 | Do not vendor compiler; use supported installed toolchain |
| https://github.com/TheAlgorithms/Rust | Engineering/test reference | P2 | Reuse concepts only after license and correctness review |
| https://github.com/rustdesk/rustdesk | Unrelated desktop application | P3 | No direct trading integration identified |
| https://github.com/tensorflow/rust | Historical ML binding reference | P3 | Archived upstream; do not choose as a new dependency without compelling compatibility evidence |
| https://github.com/exercism/rust | Agent/developer training | P3 | Learning material, not a runtime dependency |
| https://github.com/RustPython/RustPython | Alternative interpreter research | P3 | No integration unless a benchmarked requirement exists |
| https://github.com/bee-san/RustScan | Security reference | P3 | Authorized infrastructure testing only; not a trading runtime dependency |
| https://github.com/rust-unofficial/awesome-rust | Discovery/reference | P2 | Use to find candidates; each candidate requires separate due diligence |
| https://github.com/rustfs/rustfs | Research artifact storage | P3 | Consider only if storage requirement and threat model justify it |
| https://github.com/google/comprehensive-rust | Rust training | P3 | Training/reference only |
| https://github.com/rust-lang/rust-analyzer | Developer tooling | P2 | Local engineering tool; no runtime dependency |
| https://github.com/rustdesk/rustdesk-server | Unrelated desktop infrastructure | P3 | No direct trading integration identified |
| https://github.com/rust-lang/rust-clippy | Static analysis | P1 | Adopt as a development quality gate where compatible |
| https://github.com/rust-lang/rustup | Toolchain management | P2 | Developer environment only |
| https://github.com/rust-lang/rustfmt | Formatting | P1 | Adopt formatting check in Rust CI where compatible |
| https://github.com/grpc/grpc-rust | RPC interoperability | P3 | Verify maintenance, protocol compatibility and supported alternatives before use |
| https://github.com/rustls/rustls | TLS/security | P2 | Evaluate only for an actual Rust networking component; do not replace existing TLS casually |
| https://github.com/nikivdev/rust | Unknown/small project | P3 | Inspect README, license, activity and code before any use |
| https://github.com/rust-lang/cargo | Build/dependency tooling reference | P2 | Use supported Cargo toolchain; do not vendor Cargo |
| https://github.com/rust-lang/rust-bindgen | C interoperability | P3 | Only if an audited C API integration is required |
| https://github.com/avhz/RustQuant | Quantitative finance research | P1 | Prototype isolated math/pricing utilities; independent numerical tests and license review required |
| https://github.com/xirong/my-git | Git workflow and AI change governance | P1 | Strong reference for PR/change-control, evidence-linked review and multi-agent Git workflows; documentation only until its practices are reconciled with AURELIA's existing controls |
| https://github.com/GitAlias/gitalias | Developer productivity | P3 | Optional local Git aliases; inspect alias definitions and user shell impact before adoption; not a runtime dependency |
| https://github.com/actions/actions-runner-controller | CI runner infrastructure | P2 | Kubernetes operator for scalable self-hosted GitHub Actions runners; deploy only if an existing controlled Kubernetes cluster, admin ownership, isolation and patching plan are available; never expose Deriv credentials to repository research jobs |
| https://github.com/inversify/InversifyJS | TypeScript dependency injection | P3 | Optional only if AURELIA has a TypeScript service that benefits from IoC; upstream README says future work/releases are moving to inversify/monorepo, so evaluate that canonical destination before any dependency adoption |

## 4. Recommended execution sequence

1. Resolve each upstream's default branch to a full immutable commit SHA and capture license, release/activity and dependency metadata.
2. Read README, contribution/security policy, manifest files, build scripts, tests and CI workflows before running any code.
3. Run security and compatibility triage; close or defer irrelevant projects.
4. Build an isolated proof of concept for only the highest-value candidates: RustQuant, Eiten, Clippy, rustfmt, and optionally SIE after a concrete inference requirement is defined.
5. For quant candidates, reproduce baseline results before changing methods; add cost-aware chronological OOS and robustness tests.
6. Produce a component-by-component integration proposal with measured benefit, operational cost, risk, rollback plan and test evidence.
7. Open a PR with evidence artifacts; independent reviewer and CI must pass before any merge.
8. Keep production qualification separate: authenticated Deriv session, broker-derived minimum-stake validation, verified transaction lifecycle/reconciliation, strategy qualification, calibration/cost validation, 3,600-second soak and production runtime evidence remain separate gates.

## 5. Acceptance criteria

An intake item may be marked **Accepted for prototype** only when commit SHA, license, dependencies, tests, and security triage are recorded. It may be marked **Integrated** only after reviewed PR and CI evidence. It may be marked **Production-qualified** only after system-level tests and explicit release authorization. No agent leaderboard score, repository popularity, green unit test alone, or simulated trade can substitute for these gates.

## 6. Current execution record

- GitHub repository metadata was checked for all 27 supplied upstreams on 2026-10-14; all were reported public/readable by the connected GitHub tool.
- `tensorflow/rust` was reported archived.
- The connected GitHub account reported write permission on `Anto-30/aurelia-trading`; upstream repositories were read-only.
- This document is a planning/intake artifact. It does not assert that repositories were cloned, dependencies installed, tests executed, production secrets provisioned, or trading qualification completed.


## 7. Actual tool / plugin availability assessment (2026-10-14)

**Available and exercised in this run**
- GitHub connector: repository metadata reads, branch creation, file creation/read-back, and draft PR creation. PR #128 is open as a draft.
- Web research: public project documentation used to classify Eiten, SIE and RustQuant.
- Installed skill library: public-equity-investing router was read; it is relevant to Eiten's listed-equity portfolio research but is not a substitute for a derivatives-specific validation workflow.

**Useful installed skills for subsequent work**
- `data-analytics/index`: route dataset, metric and research tasks.
- `data-analytics/analyze-data-quality`: check data freshness, grain, missingness, duplication and leakage risks.
- `data-analytics/validate-data`: validate methodology, calculations, source provenance and conclusions.
- `data-analytics/visualize-data`: quantitative charts for reports and durable artifacts.
- `public-equity-investing/idea-generation`: use only for the equity/portfolio component of Eiten; do not generalize results to synthetic indices or Deriv products.
- `supabase/supabase`: mandatory before any task that changes or queries AURELIA's Supabase schema/data.
- `notion/notion-spec-to-implementation`: optional only if a relevant Notion specification is actually available and connected.
- GitHub connector and repository-local CI: source-control/evidence channel; use PRs and branch isolation.

**Not confirmed available in this session**
- A local shell/worktree with the Rust compiler, Cargo, Python environments or containerized build sandbox for these repositories.
- An authenticated Claude Code, Grok, JEV or Dev AI execution session that can be directly assigned tasks from this chat.
- Permission to install tools on the user's workstation or cloud worker, configure agent credentials, provision third-party API keys, or create GitHub secrets.
- Passing workflow runs for this documentation commit; the GitHub workflow-run query returned no runs for the commit.

Therefore, this run establishes a reviewed plan and draft PR, but does not claim to have provisioned external agents, installed local toolchains, cloned repositories, or run source-level tests. To equip the execution environment, the responsible developer/agent must install the toolchain in an isolated runner and attach logs/artifacts to the PR. No credentials should be shared in chat or committed to the repository.


## 8. Additional source inspection and CI check

Read-only source inspection performed after the initial draft:
- `tradytics/eiten`: README describes a Python equity-portfolio toolkit with eigen, minimum-variance and maximum-Sharpe portfolios, genetic-algorithm portfolios, Yahoo Finance data loading, and a historical-return simulator. Treat as equity portfolio research; not direct evidence of a validated Deriv synthetic-index strategy. Upstream default branch reported as `master`.
- `superlinked/sie`: README describes the Superlinked Inference Engine, a self-hosted inference server with OpenAI-compatible endpoints and support for multiple model/task types. Treat as optional infrastructure only after a measured latency/cost/security comparison; upstream default branch reported as `main`.
- `avhz/RustQuant`: `Cargo.toml` declares a Rust quantitative-finance workspace, version 0.4.0, edition 2021, dual-licensed `MIT OR Apache-2.0`, with crates under `crates/*`, examples, and bindings. This is manifest evidence only, not build/test evidence. Upstream default branch reported as `main`.
- AURELIA GitHub combined commit status query for the latest manifest update returned no status entries. No passing CI run was established for this documentation commit.

## 9. Completion boundary and blockers

Completed in this session: a dedicated branch and draft PR; documented role/tool/skill mapping; read-back verification of the intake file; targeted read-only inspection of three candidate repositories; and a GitHub commit-status check.

Not completed or not verifiable in this session: immutable SHA pinning for all 23 repositories; full README/license/source review of all 23; cloning or installation; dependency/security scans; builds and tests; quant backtests; actual assignment/execution by external agents; environment/toolchain provisioning; CI execution; independent human review; merge; or production qualification.

Reason: the available connected GitHub tool provides remote source-control operations and read-only file access, but no confirmed local shell/worktree or authenticated execution sessions for Claude Code, Grok, JEV, or Dev AI. Do not mark these items complete without a connected runner/agent and its verifiable logs.

Next authorized work should start with a controlled GitHub Actions or dedicated isolated runner that checks out pinned commits, installs only audited dependencies, runs repository-specific tests, uploads logs/SBOM/license reports, and opens follow-up PRs. Do not place Deriv credentials in runner environments for repository research. Keep `LIVE_LOCK` unchanged.


## 10. Immutable upstream snapshot pins (retrieved 2026-10-14)

The first 23 rows below are the initial intake batch. The four additional repositories supplied afterward are pinned in the supplemental table at the end of this section.

These full commit SHAs pin the exact default-branch snapshots observed during intake. They are **source identity pins only**; they do not imply the projects have passed license review, security scanning, compilation, tests, or AURELIA integration. Branches may advance after this snapshot.

| Repository | Observed default branch | Pinned commit | Commit date (UTC) |
|---|---|---|---|
| https://github.com/tradytics/eiten | master | `44536c58887833b7b9bbcb30f2a270db2c712ea6` | 2020-09-21 |
| https://github.com/superlinked/sie | main | `03dd3fd3c79535cfcc052ea3be379c87413d7962` | 2026-10-14 |
| https://github.com/rust-lang/rust | main | `d8ef4f3fe7031514cbd7d056b7b058814987ecec` | 2026-10-14 |
| https://github.com/TheAlgorithms/Rust | master | `fed66cb0c74c4a939ec5163648458a8c2b46fd4c` | 2026-10-08 |
| https://github.com/rustdesk/rustdesk | master | `256dc9bc12c717dea84f6a41371c67acc47edb62` | 2026-10-14 |
| https://github.com/tensorflow/rust | master | `1ddf5a348037402f87d67c076bf3019857eae05f` | 2025-01-12 |
| https://github.com/exercism/rust | main | `cc099ae090a6acbe6f53f1e36325263046ba333e` | 2026-10-09 |
| https://github.com/RustPython/RustPython | main | `016ed92f9ef919125781842537c299fd4bbd250d` | 2026-10-14 |
| https://github.com/bee-san/RustScan | master | `937903340aa6266abb26e93ea3241026b3fd8150` | 2026-10-05 |
| https://github.com/rust-unofficial/awesome-rust | main | `42c574875b21266f4667442ca80d10582c0183b1` | 2026-10-14 |
| https://github.com/rustfs/rustfs | main | `08ac1ec21808e29ab69bdfe3ec4bd16e43051e22` | 2026-10-14 |
| https://github.com/google/comprehensive-rust | main | `1b82ec405d6346932e10363248b23cd6e38df050` | 2026-10-06 |
| https://github.com/rust-lang/rust-analyzer | master | `dd5ed69d4b5b26fe7f91013b1d02608cd37ae199` | 2026-10-12 |
| https://github.com/rustdesk/rustdesk-server | master | `873230e35a8805de7fd057e7eb763c46f7a174ef` | 2026-10-10 |
| https://github.com/rust-lang/rust-clippy | master | `4fc115b7d555c8057e1736871c592aa45831b02a` | 2026-10-13 |
| https://github.com/rust-lang/rustup | main | `fa0650ae0931f1f38d77310b7ff9b00aa3523486` | 2026-10-14 |
| https://github.com/rust-lang/rustfmt | main | `c69af7786cdfef5da968f53eebd6c9b1af242b5f` | 2026-10-14 |
| https://github.com/grpc/grpc-rust | master | `17352c8233cf0280d16a24343f2f568b7d31eae4` | 2026-10-13 |
| https://github.com/rustls/rustls | main | `f238d682f46a64d089d5a0fc3607ef2073fb145f` | 2026-10-14 |
| https://github.com/nikivdev/rust | main | `0d4c744eb9624f2d85fa7b1f9e5bf37647282713` | 2026-01-20 |
| https://github.com/rust-lang/cargo | master | `377340976b3fafadb61a78ef192665518f085c57` | 2026-10-14 |
| https://github.com/rust-lang/rust-bindgen | main | `841f911a8085dcf6fad69ddd67d17f0f6d8f8e24` | 2026-10-14 |
| https://github.com/avhz/RustQuant | main | `8a7e038c7563e77bf5f5a973ef673316a40f3b3d` | 2026-10-04 |

Snapshot method: GitHub repository metadata provided each default branch; the GitHub commit API returned the full SHA and committer date for that branch at lookup time. No code was cloned or executed by this pinning step.


### Supplemental pins for the four additional repositories

| Repository | Observed default branch | Pinned commit | Commit date (UTC) | Initial triage |
|---|---|---|---|---|
| https://github.com/xirong/my-git | master | `5fc8f5baf97b7c5efd7f9eb3da98ed75303a2438` | 2026-09-09 | P1 — governance/change-control reference; root LICENSE is MIT; documentation inspection only |
| https://github.com/GitAlias/gitalias | main | `7653169af41a9fa93d6f5c5e2aedb4c7ce801840` | 2026-08-06 | P3 — optional local developer aliases; root LICENSE file not found at checked paths, so license remains unresolved; no runtime integration |
| https://github.com/actions/actions-runner-controller | master | `5aed393af8a412f6b0fe27507713687a6beeb000` | 2026-10-02 | P2 — Apache-2.0; infrastructure candidate only if a controlled Kubernetes runner environment is available |
| https://github.com/inversify/InversifyJS | master | `fdd9186891e777884012984c64c271e576155f08` | 2025-11-19 | P3 — MIT; TypeScript IoC candidate; README points future development/releases to inversify/monorepo |

These are immutable source identity pins, not security, build, test or integration approvals. The metadata and README reads were performed through the connected GitHub tool; no upstream code was executed.


### Supplemental license and source notes

- `xirong/my-git`: README describes a Git and AI-native engineering governance handbook; the checked root `LICENSE` is MIT. Suitable as a process reference, not executable runtime code.
- `GitAlias/gitalias`: README describes shell/Git command aliases; a root license file was not found at the checked `LICENSE`, `LICENSE.md`, or `LICENSE.txt` paths. Treat the license as unresolved until the repository's authoritative licensing terms are located; do not copy/distribute its contents as a dependency yet.
- `actions/actions-runner-controller`: README describes a Kubernetes operator that provisions/scales self-hosted GitHub Actions runners; the checked root license is Apache-2.0. This is infrastructure, not an agent or an automatically available runner; deployment requires cluster administration, identity/permissions, patching, isolation, and operational ownership. GitHub's current documentation describes ARC as a Kubernetes-based way to host self-hosted runners: https://docs.github.com/en/actions/concepts/runners/actions-runner-controller.
- `inversify/InversifyJS`: README describes a TypeScript/JavaScript inversion-of-control container; the checked root license is MIT. Its README directs future development and releases to `inversify/monorepo`; inspect that destination before adopting a new dependency.


## 11. Additional repositories supplied on 2026-10-14

These repositories were checked for public metadata and their default-branch snapshots were resolved. Snapshot pins identify source only; no claim of build, security, license, or integration qualification is implied.

| Repository | Default branch | Snapshot commit | Proposed use / disposition |
|---|---|---|---|
| https://github.com/xirong/my-git | master | `5fc8f5baf97b7c5efd7f9eb3da98ed75303a2438` | **P1 governance reference.** README focuses on AI-native Git change control, evidence-backed reviews, collaboration, branch protection and multi-agent work. Adapt process concepts; do not import blindly. |
| https://github.com/GitAlias/gitalias | main | `7653169af41a9fa93d6f5c5e2aedb4c7ce801840` | **P2 developer ergonomics.** Git aliases only; optional local developer setup, not a runtime dependency or security control. Review aliases before adopting. |
| https://github.com/actions/actions-runner-controller | master | `5aed393af8a412f6b0fe27507713687a6beeb000` | **P2 infrastructure research / high operational cost.** Kubernetes operator for self-hosted GitHub Actions runner scale sets. Do not deploy solely for this intake; requires Kubernetes administration, runner isolation, patching and least-privilege controls. A GitHub-hosted runner is simpler for non-sensitive repository checks. Never expose Deriv secrets to untrusted repository builds. |
| https://github.com/inversify/InversifyJS | master | `fdd9186891e777884012984c64c271e576155f08` | **P3 conditional.** TypeScript/JavaScript inversion-of-control container. README notes development moving to the Inversify monorepo. No AURELIA integration identified; defer unless a concrete TypeScript service requires it. |

Metadata and README checks are not source audits. These four upstreams are read-only to the connected GitHub account; no changes were made upstream.
