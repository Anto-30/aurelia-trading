# External Repository Intake — Batch 2 (2026-10-14)

**Repository:** `Anto-30/aurelia-trading`  
**Disposition:** preliminary metadata/README triage; all sources remain unapproved and uninstalled.  
**Authority boundary:** this intake does not add source code or dependencies to the AURELIA runtime, change `config/LIVE_LOCK.yaml`, grant external agents production credentials, or authorize broker transactions.

## Scope and evidence standard

The user supplied the 13 repositories below. This document records a preliminary capability fit and the review required before any use. It is **not** a full source audit, a vulnerability-free assertion, a legal license opinion, a pinned-source registry update, or evidence that tools were installed or executed. Exact default-branch commit SHAs, complete license files/notices, transitive dependency inventories, security scans, and reproducible isolated tests remain pending for every candidate unless explicitly noted.

## Preliminary disposition

| Repository | Potential role in AURELIA | Preliminary mode | Required gates / key risks |
|---|---|---|---|
| [ifixai-ai/iFixAi](https://github.com/ifixai-ai/iFixAi) | Independent agent evaluation, policy/permission and prompt-injection testing | `SANDBOX_ONLY` | Review evaluator methodology, fixture coverage, telemetry/data egress, provider credentials, package supply chain, and license at exact pinned commit. Use synthetic fixtures first; scores are not proof of trading correctness. |
| [usestrix/strix](https://github.com/usestrix/strix) | Authorized security testing of AURELIA's non-production web/API surface | `SANDBOX_ONLY` | Offensive scanner; test only against explicitly authorized, isolated targets. No broker endpoints, production account, live secrets, or internet-wide targets. Review container privileges, command execution, egress, model/provider credentials, and reports before any run. |
| [PostHog/posthog](https://github.com/PostHog/posthog) | Product/runtime observability and analytics | `REFERENCE_ONLY` pending need | Upstream describes analytics, replay, flags, errors and logs; core MIT licensing has exceptions including `ee` paths with separate licensing. Review data minimization, self-hosting footprint, telemetry, retention, residency, authentication, and per-directory licensing. Never use as broker ledger or execution authority. |
| [hackerai-tech/hackerai](https://github.com/hackerai-tech/hackerai) | Unconfirmed from supplied URL alone | `REFERENCE_ONLY` | Identity, purpose, default branch, source integrity, license, dependency manifests, maintainer activity, and security posture require direct repository verification before classification or execution. |
| [latitude-dev/latitude-llm](https://github.com/latitude-dev/latitude-llm) | LLM prompt/evaluation/observability workflow candidate | `SANDBOX_ONLY` | Verify current project scope and exact license; assess prompt/data retention, provider-key handling, user isolation, model-call egress, auth, migrations, and dependencies. No access to broker credentials or production datasets. |
| [nrwl/nx](https://github.com/nrwl/nx) | Build/test orchestration and monorepo tooling | `TOOLCHAIN_ONLY` | Establish actual monorepo/build need first. Pin Nx and plugins; inspect task execution, cache poisoning/remote-cache trust, plugin lifecycle scripts, CI token scope, and license of each plugin. No production deployment or secret access from untrusted PRs. |
| [tanviet12/vbsec](https://github.com/tanviet12/vbsec) | Unconfirmed security-related candidate | `REFERENCE_ONLY` | Verify repository identity, purpose, exact commit, license, dependencies, and any scanning/exploitation behavior. Do not execute until isolated threat-model and authorization review is complete. |
| [RaiAnsar/claude_code-multi-AI-MCP](https://github.com/RaiAnsar/claude_code-multi-AI-MCP) | Multi-provider agent/MCP orchestration reference | `SANDBOX_ONLY` | MCP tools and provider adapters are untrusted input boundaries. Inspect tool schemas, arbitrary command/file/network capabilities, prompt-injection handling, credential storage, provider egress, and permission defaults. Do not copy unsafe permission bypasses or allow it to write to capital-plane paths. |
| [LeoYeAI/openclaw-guardian](https://github.com/LeoYeAI/openclaw-guardian) | Unconfirmed agent/security guard candidate | `SANDBOX_ONLY` | Verify what is guarded, how policy is enforced, and whether enforcement can be bypassed. Test adversarial prompts, tool-call denial, fail-closed behavior, logs, dependencies, and license. Never treat a claimed guardian as an independent release authority. |
| [hyhmrright/brooks-lint](https://github.com/hyhmrright/brooks-lint) | Linting/static-analysis candidate | `TOOLCHAIN_ONLY` pending validation | Confirm language/tool purpose and maintenance. Pin version, review plugin/code execution and configuration loading, run against a harmless fixture, compare false negatives/positives with existing checks, and review license/dependencies. |
| [ongridio/ongrid](https://github.com/ongridio/ongrid) | SRE/observability and incident investigation reference | `SANDBOX_ONLY` | README describes host agents, audited inspection tools, remote execution/browser SSH, Kubernetes lifecycle features and model/MCP integrations. This is a high-privilege boundary: never install on the production trading host or grant shell, cluster, broker, or secret access without a separate security review. README states AGPLv3 and that brand assets are not licensed under it; review `TRADEMARK.md` and all notices. |
| [0sec-labs/0](https://github.com/0sec-labs/0) | Unconfirmed security/research candidate | `REFERENCE_ONLY` | Verify repository identity, purpose, current default branch, license, dependencies, build scripts, network behavior, and security implications before use. |
| [alishobeiri/thread-notebook](https://github.com/alishobeiri/thread-notebook) | Conversation/thread knowledge capture reference | `REFERENCE_ONLY` | Verify data model, import/export paths, access controls, telemetry, persistence and deletion, prompt-injection exposure, license, and dependencies. No real broker statements, account identifiers, API tokens, or sensitive logs in test fixtures. |

## Cross-cutting gates before adoption

1. **Identity and pinning:** resolve each canonical repository, default branch, immutable 40-character commit SHA, release/version, and upstream license/notice paths. Do not treat a mutable `main`/ `master` URL as an immutable dependency.
2. **Supply chain:** inventory lockfiles/manifests, transitive dependencies, build/install hooks, container base images, licenses, known vulnerabilities, secret leaks, and provenance. Run scanners against exact pinned snapshots; report timeouts and missing coverage as incomplete, not clean.
3. **Isolated execution:** never execute candidate code with production secrets, broker credentials, SSH keys, authenticated browser profiles, or production network reachability. Use least-privilege disposable environments, egress controls, synthetic data, and resource limits.
4. **Agent/MCP threat model:** enumerate each tool's read/write scope, command execution, filesystem access, outbound network, authentication, prompt-injection resistance, audit trail, and fail-closed behavior. Tool descriptions are not enforcement.
5. **AURELIA separation:** external tools can submit research artifacts or recommendations only. They cannot alter risk thresholds, ledger truth, strategy qualification, execution adapters, the live lock, release authority, or order submission.
6. **Measurable value:** define a use case and baseline before testing; record reproducible tests, false positives/negatives, latency/resource cost, failure modes, and rollback plan. Do not add infrastructure solely because a repository was supplied.
7. **Review and release:** require independent human review, exact-commit CI, resolved license findings, and verified security boundaries. Keep changes draft/unmerged until repository branch protections and required checks are enforced.

## Priority order

- **P1 — security/evaluation in disposable CI:** iFixAi; Strix only on an explicitly authorized local fixture; inspect the multi-AI MCP and guardian projects statically before any execution.
- **P2 — build/toolchain:** Nx and brooks-lint, only if the existing build/test workflow demonstrates a gap.
- **P3 — telemetry and incident operations:** PostHog, Latitude, Ongrid, and thread-notebook only after a data-flow/privacy/privilege review and a documented operational need.
- **P4 — identity and purpose verification first:** hackerai, vbsec, and 0sec-labs/0 remain unclassified until the repository metadata and source contents are verified.

## Status

- All 13 URLs recorded for review.
- Preliminary modes are **not** admission to the canonical registry and do not authorize cloning, installation, or execution.
- No source has been copied into AURELIA's execution paths; no candidate dependency has been added to the production runtime.
- No live orders were submitted; `config/LIVE_LOCK.yaml` remains the controlling release gate and must stay fail-closed.
- Next permitted work: resolve exact repository metadata and commit pins; run static/source/license/dependency review in isolated CI; produce findings and evidence; request independent human review.

## Batch 3 — additional catalogs supplied 2026-10-14

Five additional repositories were added to the audit after immutable default-branch commit resolution:

- [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps/commit/4bf51ab704fb2c5b3803cd5191b30d7dcdb51dc2) — Apache-2.0 root license; curated app list; per-example licenses/dependencies are separate.
- [Arindam200/awesome-ai-apps](https://github.com/Arindam200/awesome-ai-apps/commit/e5065fd86b79fd48f52c0b3261b5256ae71f6eb6) — MIT root license; self-contained examples may require separate provider API keys and manifests.
- [ContextJet-ai/awesome-llm-observability](https://github.com/ContextJet-ai/awesome-llm-observability/commit/4b8383014ddd54c10d17e170a066beb3a23bdc7a) — CC0 catalog and skills; helper tracing captures prompt content by default unless configured otherwise. No AURELIA/broker data may be traced until privacy boundaries are validated.
- [hasitpbhatt/awesome-ai-apps](https://github.com/hasitpbhatt/awesome-ai-apps/commit/8c2744a62ae0f036d7c1fe179c0683246e25e3ee) — MIT curated index; linked apps remain individually unreviewed.
- [vonzosten/awesome-LangGraph](https://github.com/vonzosten/awesome-LangGraph/commit/68509d7485a280eea0e638ef86428dd9a61fbea1) — CC0 curated list with unlocked npm maintenance tooling and GitHub API calls; do not pass privileged AURELIA tokens to the tooling.

The immutable pins, README/LICENSE blob hashes, root manifest and lockfile observations, dispositions and expanded risks are recorded in [EXTERNAL_REPOSITORY_AUDIT_2026-10-14.md](EXTERNAL_REPOSITORY_AUDIT_2026-10-14.md). Total candidates covered by that preliminary audit: 18. No candidate was installed or added to AURELIA runtime; full code-level review, CVE/SBOM scans and legal checks for each linked project are still incomplete. All remain reference/sandbox/toolchain-only, not production dependencies.
