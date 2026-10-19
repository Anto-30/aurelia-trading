# External Repository Intake — Batch 3
Date: 2026-10-14
Parent review: [PR #136](https://github.com/Anto-30/aurelia-trading/pull/136)
Scope: immutable source snapshots and initial README/license/tree triage for five user-supplied AI/LLM resource repositories.

## Evidence and limitations
Source commit pins below were resolved from each repository's `main` ref on 2026-10-14. README and LICENSE blobs were fetched at the corresponding commit. This is catalog triage, not a complete code audit, legal opinion, SBOM, or vulnerability scan. No source code or dependency was installed or executed. No candidate is approved for production use. Resource lists point to third-party projects with their own code, licenses, permissions, dependencies, and security posture; evaluate each selected downstream project separately.

## Immutable pins and findings

| Repository | Immutable commit | README blob SHA | LICENSE / blob SHA | Scope and disposition |
|---|---|---|---|---|
| [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps/commit/4bf51ab704fb2c5b3803cd5191b30d7dcdb51dc2) | `4bf51ab704fb2c5b3803cd5191b30d7dcdb51dc2` | `e8b91511659f82c52ef8d5c1ce5cd6aabea03c19` | Apache-2.0; `261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64` | Large catalog of agent, RAG, MCP and voice examples (2,531 tree entries). Useful for discovery. Review and pin one example at a time; provider keys, arbitrary tool access, code execution, data egress, and transitive dependencies vary by example. CATALOG_ONLY. |
| [Arindam200/awesome-ai-apps](https://github.com/Arindam200/awesome-ai-apps/commit/e5065fd86b79fd48f52c0b3261b5256ae71f6eb6) | `e5065fd86b79fd48f52c0b3261b5256ae71f6eb6` | `0148de487e3b1cd67e494d5f291c1b872c949f9d` | MIT; `c1bcb65f6f0736abe6efad76f78b844a18644fba` | Catalog of RAG, agents, voice, MCP, memory and fine-tuning examples (2,583 tree entries). Root includes `skills-lock.json`, but that does not establish security of every project. Audit selected project dependencies, scripts, provider/network scopes, license notices and data handling. CATALOG_ONLY. |
| [ContextJet-ai/awesome-llm-observability](https://github.com/ContextJet-ai/awesome-llm-observability/commit/4b8383014ddd54c10d17e170a066beb3a23bdc7a) | `4b8383014ddd54c10d17e170a066beb3a23bdc7a` | `0bef6c5d3cd3d82b6d15c141504e087e29eaa945` | CC0 1.0; `9373cd5d544afbafd2156b98bb95d19225965ac0` | Observability catalog plus 26 agent skills, scripts, validation cases and `install.sh` (126 tree entries). Most directly relevant to AURELIA's LLM tracing/evaluation research, but installer and each skill must be inspected before copying. Any traces must redact secrets/account identifiers and avoid logging broker credentials or sensitive financial data. CATALOG_ONLY; skill candidates may enter isolated review. |
| [hasitpbhatt/awesome-ai-apps](https://github.com/hasitpbhatt/awesome-ai-apps/commit/8c2744a62ae0f036d7c1fe179c0683246e25e3ee) | `8c2744a62ae0f036d7c1fe179c0683246e25e3ee` | `ef504b6333bcb79493f0061d48f05151990427cf` | MIT; `79a61cd49383094563414b21380b2399c7282fc1` | Lean curated list of 134 AI apps across 11 categories (36 tree entries), not the same project as Arindam200's similarly named catalog. Useful as a discovery index; validate links, provenance, downstream licenses and project health before adoption. CATALOG_ONLY. |
| [vonzosten/awesome-LangGraph](https://github.com/vonzosten/awesome-LangGraph/commit/68509d7485a280eea0e638ef86428dd9a61fbea1) | `68509d7485a280eea0e638ef86428dd9a61fbea1` | `bda0c396e4f3bc0ea7a71ff2d3f738472fb11417` | CC0 1.0; `1625c1793607996fcfc46420e8aa2f3d2b7efd1e` | Focused LangChain/LangGraph ecosystem index (15 tree entries). Useful for mapping stateful agent, tooling, observability and evaluation options. Treat listed projects as untrusted third-party candidates; validate each one independently. CATALOG_ONLY. |

## Recommended AURELIA use
1. Use the lists for architecture research only; do not bulk-import repos, skills, or dependencies.
2. For each selected downstream project, pin an immutable commit, inspect its complete license and dependency manifests/lockfiles, scan advisories and transitive licenses, review installer/setup scripts, tool schemas, subprocess and filesystem access, network egress, and secret/data handling in a no-secrets isolated runner.
3. Prefer the ContextJet observability/evaluation concepts as a research shortlist, not as an automatic install. Establish a redacted trace schema, retention policy, access control, and tests proving tokens, account IDs, balances and broker payloads are not emitted.
4. Any strategy-research code must remain outside the capital plane. Agent frameworks and skills cannot submit orders, change release authorization, edit `LIVE_LOCK`, or decide to promote themselves.
5. Record scan tool/version, timestamp, exact source and lockfile hashes, findings and reviewer. Unavailable scanner output is INCOMPLETE, never a clean result.

## AURELIA readiness separation
This catalog review does not address or satisfy repository ruleset enforcement, production-secret isolation, authenticated Deriv account evidence, broker-derived minimum stake, strategy-specific OOS qualification, calibration/cost validation, persistent production runtime, or production 3,600-second soak. PR #136 must remain draft until its independent review and required security/dependency checks are complete. Keep `config/LIVE_LOCK.yaml` fail-closed; no merge or live authorization follows from catalog inspection.

Status: five immutable source pins and README/LICENSE metadata recorded; no dependencies installed; full dependency/security scans not run; no adoption approval.
