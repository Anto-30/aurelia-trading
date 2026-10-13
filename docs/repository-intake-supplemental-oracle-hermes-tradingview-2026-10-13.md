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


## Registration and CI update (2026-10-13 UTC)

- Added the 18 candidates not already present and refreshed the observed pins for the two candidates already registered (`Mathieu2301/TradingView-API` and `stablyai/orca`) in `config/external_repo_federation.json`. Registry count is now 327; exact repository-name duplicates: 0.
- Added four deterministic routing rules to `config/repo_agent_routing.json` for oracle/market-data sources, crypto market-making code, agent runtimes/orchestration, and reference/out-of-scope repositories. All registered repository agent references resolve to known agent IDs in the config-level validation.
- Expanded `.github/workflows/repository-intake-supply-chain-audit.yml` from 10 to 30 pinned source snapshots, added the routing config to workflow path triggers, increased the job timeout to 90 minutes and adjusted bounded archive/uncompressed-data limits. This is a code change to the audit gate, not a successful scan result.
- Static consistency check performed against the checked-out GitHub file contents: 30 workflow pins, no duplicate workflow pins, every workflow pin matches a registry `head_commit`, 327 registry entries, no duplicate repository keys, and no unknown agent IDs in registry assignments.
- CI observed for head commit `62f219ba8c775cda269414dd0c5a59cb47d42ba4`: Agent Federation Audit and gstack Workflow Federation Assurance completed successfully. AURELIA Assurance and Repository Intake Supply-Chain Audit were pending at the last check; the Continuity Watchdog was still in progress. The supply-chain audit had not yet exposed a job result, so no dependency/security scan pass is claimed.
- No source code from the candidate repositories was installed, executed, vendored, or granted production access. The existing PR remains draft pending the CI results, source-level audit evidence, and independent human review. No reviewer had submitted a review at the last check; an available authorized reviewer identity was not established by the current connector context.

### Still blocking admission

1. Wait for the 30-repository pinned-source audit to complete; inspect its artifact and all OSV/ScanCode findings. Any incomplete archive inventory or scanner failure blocks admission.
2. Verify exact advisory applicability and license obligations at pinned revisions; complete the transitive dependency/SBOM and executable-config review.
3. Run component-specific tests in a disposable, credential-free environment. For market-data sources test timestamps, staleness, symbols, terms/rate limits and fail-closed behavior; for agent gateways test auth, remote exposure, tool scope, prompt injection and secret isolation; for trading code use mocks only.
4. Obtain an independent human review and explicit approval before moving any candidate out of its present registry mode.
5. Keep the PR draft and do not merge until all required CI and human-review gates pass.


## Latest supply-chain audit result and disposition (2026-10-13 UTC)

- Latest observed 30-source audit run: [run 38433360726](https://github.com/Anto-30/aurelia-trading/actions/runs/38433360726), commit `1bd7015209ddbe536f5e2f482769adc0b6a06917`. The job completed with **failure by design of the fail-closed acceptance gate**, not a clean pass.
- The pinned-source inventory found 28 of 30 archives complete. `openclaw/openclaw` and `stablyai/orca` exceeded the configured archive download cap; those snapshots are not fully inventoried. Do not treat them as scanned or cleared. Raising resource limits blindly is not approved; first evaluate repository size, archive expansion, and whether a bounded Git-tree/path inventory can cover them safely.
- OSV-Scanner produced a report containing 2,278 vulnerability records across 271 distinct vulnerable package coordinates. The job log includes critical/high-severity examples such as Next.js Image Optimization API RCE (GHSA-2xp9-vwfh-vxw4) and Tinypool worker-options prototype-pollution RCE (GHSA-5gmw-xhrv-c9v3). These are **scanner detections requiring triage**, not yet proof that each dependency is reachable or exploitable in AURELIA. Before reuse, resolve exact repository, lockfile, package version, advisory affected range, dependency reachability, execution path, and fixed release. Do not suppress or waive the records just to make CI green.
- ScanCode emitted a JSON report covering 76 files and 40 license-expression detections. Expressions included MIT, Apache-2.0, AGPL-3.0, BSD, BSL-1.1, OFL-1.1, and proprietary-license detections, including mixed expressions. Automated detections are not legal clearance. Confirm exact file-level license, source headers, copied/vendored material, package metadata, and intended use; route AGPL/proprietary/mixed-license findings for explicit legal review before reuse.
- The artifact was uploaded as [repository-intake-supply-chain-audit](https://github.com/Anto-30/aurelia-trading/actions/runs/38433360726/artifacts/11831333784), SHA-256 `866be127ee071be59a8617d9330cbfa25d3df6244ee27917277bb8ebed0b002a`, with 14-day retention. It must be preserved/reviewed while available; the workflow log confirms the acceptance gate failed for the two incomplete inventories and OSV findings.
- On the same current branch snapshot, gstack Workflow Federation Assurance, AURELIA Agent Federation Audit, and Continuity Watchdog completed successfully. AURELIA Assurance was still running at the last status check; earlier runs were cancelled as the PR head advanced. Recheck current-head CI after the next commit rather than reusing statuses from older SHAs.
- The PR remains draft and unmerged. No independent human review submission or requested reviewer is recorded. Reviewer assignment cannot be completed safely until a real, authorized GitHub user/team is established; do not fabricate a reviewer identity.
- No candidate source was installed or executed; no production secrets, LIVE_LOCK, capital-plane, or live-order authorization settings were changed. All 20 supplemental candidates remain unapproved for production use.

### Required follow-up gates

1. Triage the OSV report by repository and package coordinate, prioritizing critical/high severity; document affected/fixed versions and disposition. Upgrade/fork or exclude candidates only after verifying the fix and regression tests. Keep unresolved candidates research-only.
2. Resolve full-inventory coverage for OpenClaw and Orca using a bounded, auditable method; do not mark either complete until the exact pinned source has verifiable coverage and hashes.
3. Review ScanCode JSON per file and resolve mixed/AGPL/proprietary expressions with a documented license decision.
4. Re-run the full audit on the latest PR head, inspect uploaded reports, and ensure every acceptance criterion passes or has an explicit fail-closed disposition.
5. Complete isolated component tests and obtain authorized independent human review. Keep the PR draft until then; do not merge or alter the capital/execution safety boundary.
