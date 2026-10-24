# Free LLM API Repository Intake — 2026-10-24

## Scope and evidence boundary

This is a preliminary, README-based intake for two repositories supplied for AURELIA's federated-toolchain research. Public README pages were inspected on 2026-10-24. This is not a source-code security audit. No repository was cloned or executed, no dependencies were installed, no API keys were entered, and no provider endpoint was called. Default-branch tip SHAs, lockfiles, workflows, update paths, runtime network behavior, SBOMs, vulnerability scans, and tests have not yet been verified.

## Repositories

### 1. tashfeenahmed/freellmapi

Source: https://github.com/tashfeenahmed/freellmapi

The README describes a self-hosted Node-based router exposing an OpenAI-compatible API and other API-compatible surfaces, aggregating multiple third-party provider free tiers. It advertises encrypted provider-key storage, automatic failover/routing, a signed model-catalog feed, a dashboard, and an MCP interface that can expose inference and routing-management functions. The README says the software is MIT-licensed and also describes a paid live-catalog service. All capacity, provider-count, encryption, and performance statements remain upstream claims until independently verified.

**Potential fit:** candidate local inference gateway for non-sensitive research, model comparison, and development-time agent routing. It may reduce per-agent configuration complexity.

**Risks / checks required:**
- A single gateway centralizes provider credentials and expands the blast radius of a compromise.
- Prompts, source code, and tool output routed to external providers leave the local trust boundary; provider terms, retention, training use, regional processing, and incident response must be assessed per provider.
- Signed catalog integrity is not equivalent to safety of the catalog entries or provider endpoints; inspect signing-key rotation, rollback protection, parser validation, and update failure behavior.
- Review MCP tool permissions carefully. Do not expose configuration/key-management or routing-management tools to agents without least-privilege controls and explicit authorization.
- Inspect authentication, session management, request logging/redaction, CORS, network binding, TLS/reverse-proxy assumptions, SQLite permissions, encryption-key lifecycle, backups, and import/export paths.
- Confirm provider free-tier eligibility, quotas, endpoint/model availability, and commercial-use terms independently; free tiers can change or be revoked.
- Verify current default-branch SHA, package lockfile, install/update scripts, CI workflows, transitive dependencies, and tests before isolated build validation.

**Disposition:** RESEARCH_ONLY / QUARANTINED pending source audit and isolated validation. Do not use as an AURELIA production dependency or route secrets, broker credentials, private trading data, or capital-authorizing commands through it.

### 2. open-free-llm-api/awesome-freellm-apis

Source: https://github.com/open-free-llm-api/awesome-freellm-apis

The README describes a curated directory of free and limited-credit LLM API providers, model identifiers, rate limits, context-window claims, API-key links, and configuration snippets. It says the directory is refreshed daily and is MIT-licensed. These are catalog-maintainer claims, not independent confirmation that every endpoint currently works or that each advertised tier is permanently free.

**Potential fit:** read-only discovery input for a provider/model registry and human-reviewed candidate shortlist. It is not itself an inference gateway or a provider trust guarantee.

**Risks / checks required:**
- Provider availability, rate limits, model names, card/phone requirements, regional access, and terms can change quickly; verify against each provider's official documentation.
- Treat copied configuration snippets and links as untrusted input. Never paste credentials into third-party forms or commit them to code.
- Avoid automatically importing model/provider entries into production routing. Require provenance, official-source confirmation, explicit data-handling review, and a versioned allowlist.
- Inspect the data format, update automation, source attribution, and any generated config before using it in an agent bootstrap workflow.
- Verify current default-branch SHA and license file before redistribution or automated reuse.

**Disposition:** READ_ONLY_DISCOVERY_ONLY. Use to generate a candidate list for review; no automatic agent configuration, credential creation, or runtime routing based solely on this catalog.

## AURELIA integration boundary

Neither repository receives capital authority. They must not be able to change risk limits, disarm the kill switch, edit release gates, access broker credentials, or submit orders. Preserve existing fail-closed invariants:

- `LIVE_EXECUTION=BLOCKED`
- `FINAL_EXECUTION_AUTHORIZATION=false`
- `capital_plane_mode=VERIFY_ONLY`
- `research_capital_authority=false`
- `external_repositories_capital_forbidden=true`

Any future test should run in an isolated, disposable environment with synthetic data and dummy credentials, network egress restricted to explicitly approved endpoints, secrets scanning enabled, and no broker/live-order permissions. A successful build or inference smoke test would not by itself authorize production use.

## Required next gates

1. Resolve and record exact default-branch tip SHAs for both repositories.
2. Inspect manifests and lockfiles, installation/update scripts, workflows, MCP/tool declarations, authentication, telemetry/logging, outbound network destinations, and license/NOTICE files.
3. Run repository-specific static analysis, dependency and secret scans, produce an SBOM, and review results.
4. Perform an isolated reproducible build and tests without real credentials; record exact commands, environment, exit codes, and artifacts.
5. For any provider used, document official endpoint source, current terms, data retention/training policy, geography, quotas, rate limits, and failure behavior.
6. Require independent human review before any deployment or integration beyond read-only research.

## Sources

- FreeLLMAPI README: https://github.com/tashfeenahmed/freellmapi
- Awesome Free LLM APIs README: https://github.com/open-free-llm-api/awesome-freellm-apis
