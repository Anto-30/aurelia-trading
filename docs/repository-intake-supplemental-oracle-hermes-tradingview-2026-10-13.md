# Supplemental Repository Intake — Oracle, Hermes, TradingView, Orchestration and Research (2026-10-13)

## Scope and disposition

This document records the 20 unique repositories supplied in the follow-up intake batch. Duplicate URLs were removed: `shner-elmo/TradingView-Screener` and `stablyai/orca` each appeared twice. Default-branch tip SHAs were resolved from GitHub's commits API on 2026-10-13 UTC. These pins identify what was inspected; they are not security approval or proof that a source was cloned, executed, installed, or tested.

**Status for every candidate: RESEARCH_ONLY / NOT_INSTALLED until a separate review explicitly changes it.** No candidate is granted capital-plane access, production secrets, broker permissions, write access to `main`, LIVE_LOCK mutation, release authority, or permission to deploy. Names such as “oracle,” “Hermes,” and “tradebot” are not evidence of fit or trustworthiness.

## Pinned candidate inventory

| Repository | Observed default branch | Pinned tip SHA | Initial classification | Preliminary disposition / main concern |
|---|---|---|---|---|
| `kOs-tile/oracle` | `main` | `1af1f3a8dc38efca399eb7e296cc8db95e4da929` | Market-context provenance / agent state | **Priority research candidate.** README describes REAL/CACHED/STALE/SIMULATED/UNAVAILABLE provenance and state endpoint. Validate source adapters, freshness guarantees, authentication, prompt injection, and fail-closed behavior; never let it replace broker truth. |
| `AstermarkLabs/Oracle` | `main` | `b0bf5020d7b66acba21ab462da32596a26a59fe7` | Unknown Oracle-named project | Hold pending README, purpose, license, dependency, and code review; do not infer fit from name. |
| `iruzen-dono/hermes-project-oracle` | `main` | `fe96bc811dce8b11d7484e30bc8dcd5969c0a0ab` | Python/CI candidate | Inspect package scope, tests, dependency pins, license and external command/network access before considering a research-only adapter. |
| `jasperan/orahermes-agent` | `main` | `027f043c47514972efb40eb9b56a98e59bc47545` | Agent/TUI candidate | Repository is comparatively large; inventory first. Keep terminal, filesystem and tool execution isolated; do not grant shell or credential access by default. |
| `gizdusum/hermes-blockchain-oracle` | `main` | `0f086e3d992e53164c279319d44c93301e9a8be1` | Blockchain/oracle candidate | Hold pending chain/source validation, RPC trust, signing/key handling, provenance, license and tests. Never treat on-chain claims as broker account truth. |
| `dultimateade/hermes` | `main` | `6ab212b3c58057255a62df75f46b3d9dc06ec916` | Agent framework candidate | Review auth, tools, memory, shell/network boundaries, plugin installation, supply chain and license before sandbox evaluation. |
| `the-oracle-keeps-the-human-human/hermes-book-oracle` | `main` | `54170bc05e03ace83554155c53c06106d4623990` | Book/content oracle | Content/reference only unless code and licensing prove otherwise; no trading runtime role assumed. |
| `shingyusik/oracle-todo` | `main` | `c4d41f5539727bbbfc5975c8913ed3968d20e0bb` | Task/agent workflow candidate | Hold pending purpose and license review; no task agent can alter release gates or capital controls. |
| `paras200/hermes-anywhere` | `main` | `fb6d567a41b76f0e124a58629118f35b78e329f0` | Remote/portable agent deployment | **High-risk sandbox-only candidate** until cloud-init, remote access, model credentials, network exposure and secret storage are reviewed. |
| `xl3v3r/hermes-oracle-memory` | `master` | `bf2199d571d572596f51b2bd946e32b73aa4ffe1` | Agent memory/context | Research-only. Test provenance, retention, poisoning, cross-agent isolation, deletion and stale-memory behavior; memory cannot authorize trades. |
| `shner-elmo/TradingView-Screener` | `master` | `5422d9012752353c59a31d13f54ceba55c265d9d` | Python market screener/data | **Priority research candidate.** README describes stock/forex/crypto/CFD/futures screening via TradingView data endpoints. Treat as external/unofficial market data; check terms, rate limits, freshness, symbol mapping, availability and failure modes. Not an execution source. |
| `shopsmartai/oracleops` | `main` | `b273da3f46bb057c5fe2a2009f02db7e6b13fe72` | Oracle DBA Hermes plugin | Out of trading scope; database diagnostic plugin. Never connect it to AURELIA production databases or secrets without a separate security need and review. |
| `Mathieu2301/TradingView-API` | `main` | `6a4f8ff9a2b332d0a59dbd27c75201eb84663045` | TypeScript market-data API | **Priority research candidate.** README labels it an independent community project, not an official TradingView API; v4 is a breaking rewrite. Pin package/version, test data integrity and rate limits, and isolate credentials/network. No live price assumption without timestamp/freshness validation. |
| `openclaw/openclaw` | `main` | `28ee33394fe3ae90b74fefeb2ddd9e30649d6432` | Multi-channel assistant gateway | **High-risk sandbox-only candidate.** Broad chat/device integrations and tool plugins expand the attack surface. Assess gateway authentication, plugin provenance, permissions, telemetry, secrets, remote exposure and command execution before any deployment. |
| `just-nilux/awesome-tradingview` | `master` | `03d16ff0366351a0eff3945afba212caa410455b` | Curated TradingView resource list | Reference-only. Links are not endorsements; review each downstream resource independently. |
| `stablyai/orca` | `main` | `9f2abd5e70517c4838282595f02d04736c273cf1` | Local multi-agent orchestration/UI | **High-risk sandbox-only candidate.** README describes parallel agents/worktrees and mobile companion. Assess local process execution, Git write scope, inter-worktree isolation, mobile/auth, secrets, network listeners and update chain. Never grant merge or release authority. |
| `Dr-Amp/adaptative-living-library` | `main` | `9689f7f080a4052469213f4ef474d8ac0dc6e057` | Unknown library/research candidate | Hold pending source purpose, license, maintenance and dependency review; no assumed trading relevance. |
| `morluto/rea` | `main` | `93e29d242ae60a3d2daec355e7a31b4a0bdd4234` | Unknown CLI/research candidate | Hold pending README and code-level review; no integration inferred from repository name. |
| `Adamant-im/adamant-tradebot` | `dev` | `9f81feaab1404961a764ddbecc6cc225c94e0b10` | Crypto market-making bot | **Do not connect to any exchange account.** README describes automated market making on centralized exchanges for token issuers. This is not a directional strategy validation. Review order placement/cancellation, inventory exposure, wash-trading/legal risk, API-key permissions, kill switch, idempotency and reconciliation in a credential-free sandbox first. |
| `storytold/wordcraft` | `main` | `159b84f54c74e9e82fb3109b758ae7dd6f4e3ab0` | Writing/editorial tool | Out of trading runtime; reference-only unless a separately scoped documentation workflow requires it. |

## Agent routing proposal (not a runtime permission grant)

| Candidate group | Proposed lead | Independent reviewer | Boundary |
|---|---|---|---|
| Market-context provenance / oracle adapters | Claude Code | ChatGPT + JEV | Research plane only; no broker-truth replacement; stale/unavailable must fail closed. |
| TradingView screener / data API | Claude Code | Grok + JEV + ChatGPT | Data ingestion and timestamped research only; check terms/rate limits; no order submission. |
| Agent frameworks, memory, remote gateways, orchestration UI | Claude Code | ChatGPT security/architecture; JEV deterministic QA; Grok independent review | Disposable sandbox only; no production credentials, unrestricted shell, Git merge, release or capital authority. |
| Crypto market-making bot | JEV for static/test design; Claude Code for isolated analysis | ChatGPT risk review + Grok market-mechanics review | Source review and synthetic tests only; no exchange keys or live orders. |
| Oracle DBA, book/content, TODO, curated list, writing tool, unknown-purpose repositories | ChatGPT triage | Claude Code + JEV | Reference-only or reject as out-of-scope until a concrete need is established. |

## Required checks before admission

1. Verify pinned commit and inspect the actual source tree, README, root and nested license/notice files, install scripts, hooks, workflows, MCP configs, package manifests and lockfiles.
2. Generate an SBOM; run secret scanning, SAST, dependency/advisory scanning and transitive license inventory. Confirm advisories apply to the exact pinned versions.
3. Test only in a disposable environment without broker credentials, production data, authenticated browsers, or write access to canonical branches.
4. For data sources, measure timestamp integrity, staleness, symbol mapping, missingness, rate limits, retry behavior and outage fail-closed semantics.
5. For orchestration and agent frameworks, test prompt-injection boundaries, tool allowlists, filesystem/worktree isolation, credential leakage, remote exposure and audit logging.
6. For any trading/exchange code, test idempotency, order/position reconciliation, cancellation behavior, risk caps and kill switch using mocks only. No live trading test is authorized by this intake.
7. Record exact evidence and require independent human review before changing any candidate from RESEARCH_ONLY.

## Evidence limits

The pins above are observed default-branch tip SHAs from GitHub on 2026-10-13 UTC. Initial purpose notes are based on repository metadata and selected README text where available. This document does **not** claim a full source audit, license clearance, SBOM, successful test run, installation, synchronization into agent workspaces, or production readiness. The registry and routing files must be updated and CI must validate the entries before this supplemental intake is considered fully registered.

## Invariants

Keep one canonical AURELIA repository, one capital plane, one release authority and one evidence lineage. Claude Code is the implementation lead; ChatGPT is architecture/assurance; Grok is independent market/news research; JEV is deterministic QA/operations. Agent rankings or successful CI cannot grant capital authority. Existing live execution remains blocked unless its separate broker, risk, calibration, soak, runtime and release evidence gates pass.
