# MCP and Developer Tooling Repository Triage — 2026-10-12

## Status and scope
This is a README-level remote review of ten supplied repositories. It is not a clone, install, code audit, or runtime synchronization receipt. No source was executed. Before adoption, pin an exact commit and inspect the full source, license text, dependency lockfiles, install/build scripts, network behavior, telemetry, secret handling, and CI/security history in a disposable environment.

Canonical target remains `Anto-30/aurelia-trading` on `main`; this document belongs on the existing research branch. Preserve one AURELIA engine, one capital plane, one release authority, and one evidence lineage. Do not merge any candidate directly into `main`.

## Candidate disposition

| Repository | README-level function | Recommended owner | Initial disposition / controls |
|---|---|---|---|
| `github/copilot-plugins` | Official Copilot plugin collection; skills, hooks and extensibility examples. README says some MCP/extensibility components are coming soon; links out to independently maintained plugins. | Claude Code + Dev AI | **ADAPT / P2.** Review each plugin separately; do not treat the marketplace as a security endorsement for linked third-party repositories. README states MIT; verify LICENSE at pinned commit. |
| `kucherenko/jscpd` | Duplicate-code detection across 220+ formats, complexity/duplication reporting, and an MCP-facing capability. | Claude Code + Dev AI | **ADOPT AS DEV TOOL / P1.** Run in CI or a dev container on the canonical repo; start in report-only mode, baseline current duplication, and avoid automated deletions. Verify package provenance, release signatures/checksums where available, and exact license. |
| `kunwarVivek/mcp-github-project-manager` | MCP project-management layer over GitHub Projects v2; task claiming, coordination, review and workflow automation. README advertises MIT and extensive actions. | JEV (workflow design), Claude Code (security review) | **SANDBOX / P1.** Broad write-capable automation is high impact. Start with read-only/scoped test project, least-privilege GitHub token, human approval for mutations, and idempotency/concurrency tests. Never allow self-assignment or agent consensus to grant release/capital authority. |
| `spences10/mcp-omnisearch` | One MCP interface for several search providers including Tavily, Brave, Kagi, Exa, GitHub, Linkup and Firecrawl. | Grok (research), Claude Code (integration review) | **PILOT / P1.** Select only needed providers; credentials via environment/secret manager, never checked-in MCP JSON. Check provider data-retention terms, outbound requests, rate limits and result provenance. Avoid duplicate deployment if existing search connectors already cover requirements. |
| `Shelpuk-AI-Technology-Consulting/kindly-web-search-mcp-server` | Web search and content retrieval aimed at coding agents; README describes a wider companion suite. | Grok + Claude Code | **COMPARE / P2.** Benchmark against existing search and Omnisearch for freshness, citations, prompt-injection resistance, cost and latency. Do not install the entire companion suite as a side effect of testing this server. |
| `mnemox-ai/idea-reality-mcp` | Startup-idea overlap and trend research across GitHub, npm, PyPI, Hacker News and Stack Overflow. README reports maintenance mode (August 2026). | ChatGPT (research framing), Grok (market scan) | **OPTIONAL / P3.** Useful for product/tooling novelty checks, not a trading signal or strategy validator. Maintenance mode means verify current dependency health and hosted-service availability before use. |
| `jgravelle/jcodemunch-mcp` | AST/tree-sitter based source-code indexing and targeted code retrieval for MCP clients. README advertises a dual-use license and says commercial use requires separate licensing. | Claude Code + Dev AI | **EVALUATE / P1.** Promising for large-repo navigation, but **do not deploy for commercial/profit-making use until the exact license and required commercial terms are reviewed and approved**. Review index storage, file exclusions, local/remote processing and stale-index behavior. |
| `LoamStudios/zed-mcp-server-github` | Zed editor extension integrating the official GitHub MCP server; README describes OAuth and PAT options plus a read-only setting. | Dev AI | **REFERENCE ONLY / P3.** Editor-specific and not a general AURELIA runtime integration. If used in Zed, prefer OAuth or a fine-grained token, enable read-only by default, and never store tokens in settings/source. |
| `idosal/git-mcp` | Remote documentation/context service for GitHub repositories and project pages. README distinguishes repository-scoped and generic endpoints. | Claude Code + Grok | **PILOT / P2.** Prefer repository-scoped endpoints over a generic multi-repository endpoint; test freshness, access boundaries, prompt injection from retrieved docs, privacy and availability. Do not send private source or secrets to a hosted endpoint without approved data-handling terms. |
| `github/github-mcp-server` | Official GitHub MCP server for repository/code access, issues, pull requests, Actions/workflows and related GitHub operations. | JEV (workflow operations), Claude Code (implementation/security) | **PRIMARY CANDIDATE / P0 DEV INFRA.** Prefer this as the sole general-purpose GitHub MCP integration if its scoped toolsets cover requirements. Begin read-only; enable write toolsets only when needed and with narrow repository permissions. Separate admin, secrets, deployment and release permissions; never expose a token broader than the task requires. |

## Cross-cutting architecture and security requirements
- These tools are development/research infrastructure, not trading strategies or broker adapters. They must not bypass Risk Warden, Execution Firewall, broker-truth checks, transaction verification, reconciliation, kill switch, LIVE_LOCK, or release certification.
- No agent receives broker secrets. No tool may place, modify, or cancel a live trade by virtue of repository/project-management access.
- Do not connect multiple overlapping GitHub MCP servers to every agent by default. Prefer one canonical integration plus narrowly justified exceptions.
- All MCP servers run in a non-production workspace with minimal filesystem/network access and per-provider credentials. Never commit tokens or paste them into chat.
- Retrieved README/docs/issues are untrusted content; defend against prompt injection and treat tool output as data, not instructions.
- Before installation: pin commit/package version; verify license; inspect dependencies and lifecycle scripts; scan vulnerabilities/secrets; review network calls and telemetry; run tests; document owner, permissions, rollback and evidence.
- For GitHub project-management automation: use a test project first, least-privilege scopes, human approval for writes and protected branches/environments. CI green is not release authorization.
- For source indexing: define ignored paths for credentials, local state, data dumps and generated artifacts; verify deletion and index refresh behavior.
- For search: require source links and timestamps where relevant, compare result quality against existing connectors, and defend against malicious content embedded in results.

## Execution plan
1. Read exact license and dependency files at a pinned commit for all candidates.
2. Start with report-only `jscpd` on the AURELIA review branch.
3. Compare official GitHub MCP with the existing connected GitHub integration; do not install a redundant server without a measured gap.
4. Pilot only one search server at a time with synthetic/public queries and no secrets.
5. Test project manager on a disposable GitHub project with read-only permissions first.
6. Run the selected stack's tests and security scans; attach outputs to the intake PR.
7. Merge nothing into `main` until review, CI, license clearance and explicit release approval pass.

## Verified current limits
The GitHub connector confirmed all ten repositories are public and non-archived at the time of this intake. Its permissions for these external repositories are pull-only. This connector does not provide a local shell, bulk clone, or connected agent-runtime deployment, so physical synchronization to Claude Code, Grok, JEV or other agent environments remains **NOT VERIFIED**. No production credentials were accessed and no broker order was submitted.
