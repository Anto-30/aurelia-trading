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

- GitHub repository metadata was checked for all 23 supplied upstreams on 2026-10-14; all were reported public/readable by the connected GitHub tool.
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
