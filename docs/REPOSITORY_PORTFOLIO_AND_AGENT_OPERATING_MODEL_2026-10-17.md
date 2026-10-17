# Repository Portfolio and Agent Operating Model
**Review date:** 2026-10-17  
**Status:** Operating plan and ownership map; not a claim that all assigned agents are connected or running.

## Executive decision

Maintain one authoritative trading system: `Anto-30/aurelia-trading`, default branch `main`. Do not create or merge a second trading engine. Keep research agents advisory and all capital-moving authority in AURELIA's deterministic capital plane. External repositories remain untrusted source material until individually accepted.

This document reconciles the GitHub repositories visible to the connected account, the existing 367-entry external federation registry, the 81-repository source-level triage completed across the original 12, AirLLM, 67 newly supplied repositories, and Odysseus, and the existing ten-role delegation registry. A registry assignment means ownership is defined; it does not prove provider connection, task execution, heartbeat, or delivery.

## 1. Account-visible repository inventory

A GitHub search for `user:Anto-30` returned four repositories. Only the canonical AURELIA repository is the active trading source of truth.

| Repository | Observed state | Disposition |
|---|---|---|
| [Anto-30/aurelia-trading](https://github.com/Anto-30/aurelia-trading) | Populated; default branch `main`; canonical repo | **Canonical AURELIA.** All trading-engine implementation, risk, execution, evidence, and release controls belong here. |
| [Anto-30/Aurelia-trading-](https://github.com/Anto-30/Aurelia-trading-) | Populated, minimal initial README/commit; no evidence found that it is authoritative | **Duplicate/legacy candidate.** Do not develop in parallel. Add a prominent archival/redirect notice only after owner review; migrate nothing automatically. |
| [Anto-30/Tales-and-trails-safaris-](https://github.com/Anto-30/Tales-and-trails-safaris-) | Empty repository; no README or commits returned | **Safaris project placeholder.** Keep separate from AURELIA. Initialize only when the user explicitly wants work on the safaris project; no code can be audited in an empty repo. |
| [Anto-30/Anto30](https://github.com/Anto-30/Anto30) | One initial commit; no README found | **Profile/placeholder repository.** No product/runtime dependency identified. |

This inventory is limited to repositories visible through the current GitHub connection and public search. It is not proof that no additional repositories exist in other accounts or organizations. The canonical repo's 367-entry external federation is a source registry, not 367 owned projects.

## 2. Existing external repository federation

The canonical `config/external_repo_federation.json` contains **367 registered external repositories** at this review: 173 `SANDBOX_ONLY`, 58 `TOOLCHAIN_ONLY`, 64 `RESEARCH_ONLY`, and 72 `REFERENCE_ONLY`. The exact source pins and per-repository agent lists remain in that file. This count is not a claim that 367 repositories have been cloned, scanned, installed, tested, or approved.

Global policy for every external source:
- No capital authority, live order submission, production secret access/logging, `LIVE_LOCK` mutation, broker transaction write, or production deployment authority.
- External code execution is deny-by-default. Research/tooling mode is not an integration approval.
- Before adoption: pin immutable commit; inspect license and notices; generate dependency inventory/SBOM; run vulnerability and secret scans; review install/build scripts and network egress; isolate execution; verify provenance and artifacts; add regression/parity tests; obtain independent review.
- A scanner timeout, missing artifact, unknown license, or inaccessible source is `NOT_VERIFIED`, never a clean result.
- Strategy source code is not strategy evidence. Require no-lookahead tests, realistic instrument/contract modelling, spread/slippage/fees/latency/reject modelling, walk-forward and prospective OOS, calibration/drift, and positive net expectancy before qualification.

The separately reviewed 12 repositories and their exact dispositions are in [the source review](EXTERNAL_REPOSITORY_SOURCE_REVIEW_2026-10-17.md) and [the recheck](EXTERNAL_REPOSITORY_RECHECK_2026-10-17.md). The [focused priority trading-source review](PRIORITY_TRADING_REPOSITORY_SOURCE_REVIEW_2026-10-17.md) adds pinned source inspection for eight order-capable/tooling candidates; it is not a full clone/build/dependency audit. In particular, XERJ is blocked pending a clean dependency audit; Nightly OpenBot is blocked pending licensing and security redesign; desktop/browser/shell agents are sandbox-only; old strategy libraries are research-only. None is approved for direct capital-plane integration.

## 3. Agent ownership and hand-off contract

Use the existing ten registered roles in `config/agent_delegation_tasks.json`. Do not create duplicate identities to make the dashboard look busier. Every task must have one accountable owner, an independent reviewer, a deadline or explicit blocked reason, and a machine-readable evidence path.

| Agent | Accountable assignment | Required inputs/tools | Deliverable and acceptance gate |
|---|---|---|---|
| **ClaudeCode** (primary engineering) | Own implementation in a dedicated branch; repair task/proof chain; integrate only accepted changes; run tests and exact-head assurance | Canonical repo, pinned issue/PR, Python/toolchain, CI logs, isolated test runner; no production secrets in PR CI | Small reviewed commits, test artifacts, exact SHA, rollback note; never self-approve a risky change or change capital policy unilaterally |
| **ChatGPT** (independent synthesis/review) | Decompose requests; reconcile source evidence; review architecture, specs, and claims independently; maintain this portfolio/assignment map | GitHub read/write for docs where available, research tools, relevant skills, source links, task/evidence schema | Evidence-backed decision memo, counterarguments, gaps, acceptance criteria; cannot claim a provider ran or grant capital authority |
| **KimiK3** (adversarial quant/review) | Challenge task ownership, research methodology, leakage, strategy metrics, and assumptions | Pinned source snapshots, datasets with provenance, experiment configuration, cost model, baseline results | Adversarial review with falsifiable tests; reject look-ahead, cherry-picked metrics, insufficient OOS, or unsupported Deriv order-book assumptions |
| **GrokBot** (coordination/intelligence) | Maintain queue visibility, identify blocked work, summarize approved external intelligence, route tasks to owners | Task queue, normalized evidence schema, source allowlist, task deadlines; no broker credentials | Queue/status report with source links, owner, blockers, and next event; never treat narrative confidence as authorization |
| **JEV** (independent verifier) | Independently check regression tests, evidence lineage, risk controls, source pin integrity, and release checklist | Exact PR SHA, test logs/artifacts, expected schema, read-only access where possible | Independent pass/fail report on same SHA; must not rely solely on author summary or reuse unverified evidence |
| **GoogleAgentSkills** (security/cloud controls) | Review least privilege, secret boundaries, identity, sandboxing, network egress, cloud/runtime configuration | Threat model, deployment manifests, secret-reference names only, audit logs; no raw secret values | Security review and threat/remediation matrix; no secret readback, token copying, or capital authority |
| **GLM** (evidence/consistency auditor) | Check evidence bundles, schema validity, claims-vs-logs consistency, missing/corrupt artifacts | Machine-readable reports, hashes, timestamps, CI logs | Validated evidence index with contradictions and provenance; missing data remains UNKNOWN |
| **PlaywrightCLI** (UI/UX verification) | Test dashboard/operator flows and verify UI state reflects actual task and runtime events | Disposable test account, mock/sandbox data, explicit browser allowlist, screenshots/logs | Reproducible UI test report; never use production account sessions to test agent controls; UI display is not runtime proof |
| **AURELIA** (deterministic risk/release authority) | Enforce policy, validate fresh broker-derived facts, maintain kill-switch/lock, reconcile ledger and transaction lifecycle | Deterministic inputs, signed/validated evidence, broker verification, audited configuration | Explicit allow/deny reason and evidence references; fail closed on stale, missing, invalid, drifted or conflicting data; never delegate authority to LLMs |
| **Dev** (runtime/infra operator) | Blocked until authorized development device or persistent host is available; then run isolated integration and deployment verification | Authorized Linux/Docker host, pinned code, non-production test configuration, protected secret manager only when owner-controlled | Host identity/health, build/test logs, persistence/restart evidence, security controls and rollback; no paid resource creation without explicit approval |

### Cross-agent execution contract

1. **Single owner:** ClaudeCode owns implementation; a different role (JEV or KimiK3, chosen by risk domain) owns independent verification; AURELIA owns deterministic capital authorization.
2. **Task protocol:** `task.created -> task.claimed -> subagent.started -> evidence.attached -> subagent.completed|subagent.failed`. Include task ID, agent identity, exact commit/source pin, timestamps, status, artifact hashes, and failure reason.
3. **No simulated liveness:** Configuration, registry entries, an ephemeral probe, or a supervisor loop is not a live agent. Require attributable process/provider evidence and heartbeat lease with expiry.
4. **Evidence quality:** Every result records question, method, environment, input hashes, source URLs/commit SHA, output hashes, tests, limitations, reviewer, and pass/fail. Redact credentials and personal data.
5. **Bounded permissions:** Research agents can propose code/config only in isolated branches. No agent can approve its own PR, merge production changes, alter `LIVE_LOCK`, access production secrets, submit broker orders, or disable safeguards.
6. **Failure semantics:** Timeout, stale lease, schema mismatch, missing artifact, non-deterministic replay, provider disconnection, or unresolved disagreement means `BLOCKED/UNKNOWN`, not success.
7. **No duplicate engines:** All strategy prototypes are research modules feeding the existing registry/validation plane. No sidecar may become an alternate execution engine or bypass Layer 6/capital authority.
8. **Phone-first workflow:** Prefer reviewable GitHub issues/PRs and CI artifacts. Do not depend on the user's Android phone as a production host. Until a persistent, authorized Linux host is available, mark runtime deployment work blocked.

## 4. Workstream routing

| Workstream | Lead | Independent reviewer | Current gate |
|---|---|---|---|
| Governance, branch rules, protected environments | GoogleAgentSkills | JEV + owner/admin | **BLOCKED:** `main` and both rulesets were observed unprotected/disabled in the latest review; no independent PR review is recorded. |
| Agent dispatch, leases, runtime proof, queue | ClaudeCode | GLM + JEV | **BLOCKED:** provider configuration and persistent runtime evidence cannot be inferred from task registry. |
| Repository supply chain (all 367 registered sources) | ClaudeCode | GoogleAgentSkills + GLM | **PARTIAL:** registry exists; every pin still needs completed artifact-backed source/license/SBOM/CVE/secret review before any candidate is admitted. |
| Quant research and strategy qualification | KimiK3 | JEV + ChatGPT | **RESEARCH ONLY:** require reproducible, cost-adjusted, no-lookahead and prospective OOS evidence by Strategy × Symbol × Regime. |
| Deriv adapter/session/account binding | ClaudeCode | JEV + GoogleAgentSkills | **BLOCKED:** authenticated verify-only lifecycle and fresh broker-derived evidence absent. |
| Capital plane, probability, stake, kill switch | AURELIA | JEV + owner | **FAIL CLOSED:** probability band is inclusive 0.55–0.75, no clipping; stake cap remains 1% of fresh verified balance; broker minimum must be source-bound. |
| Dashboard and agent visibility | PlaywrightCLI | GLM | **BLOCKED/PARTIAL:** test with mocks until real provider events and persistent runtime exist. |
| Runtime hosting, persistence, monitoring, rollback | Dev | GoogleAgentSkills + JEV | **BLOCKED:** no verified persistent authorized host; do not create paid resources. |
| External repository intake | ClaudeCode | KimiK3 + GoogleAgentSkills + JEV | **NOT APPROVED by default:** only selective source-level learning; no direct import to execution paths. |
| Documentation, status, decisions | ChatGPT | GLM + owner | Maintain exact-head links and label verified facts, inference, unknowns, and decisions separately. |

## 5. Canonical PR backlog order

Do not merge a pile of overlapping draft PRs. Reconcile overlapping changes against the current main branch and promote one coherent, reviewable change at a time.

1. **P0 Governance/secret boundary:** review and reconcile PRs #144, #139, #143 and #153; enable branch rules and protected environment controls using an authorized administrator; verify no PR/fork path can access production secrets. Do not claim protection until settings are observed after the change.
2. **P0 Fail-closed capital gate:** resolve PR #123 against current policy and tests; require fresh source-bound account/currency/balance/minimum-stake evidence. Preserve the 0.55–0.75 no-clipping probability rule and 1% stake cap. If minimum stake exceeds the budget, reject.
3. **P0 Runtime proof and persistent execution:** reconcile PRs #116, #117, #118 and #115. Require real provider processes, lease/heartbeat, task/result artifacts and persistence across restart. A green ephemeral CI probe is not deployment evidence.
4. **P1 Adapter hardening:** independently review PR #153 and its exact-head tests; verify the adapter cannot override account binding or request opcodes. Do not connect production credentials until protected environments and independent review are verified.
5. **P1 Research kernel:** review PR #152 and #148/#146 for no-lookahead, fill assumptions, costs, trade metrics, data provenance, and strategy-specific OOS. No registry promotion based only on synthetic bars or win rate.
6. **P1 External supply chain:** PRs #122, #150, #151, #155, #136 and #132 should be consolidated where appropriate. Keep PR #155 documentation-only and draft until review; inspect exact artifacts from pinned supply-chain workflows.
7. **P2 Research backlog:** PRs #131, #125 and #124 remain research-only until exact-head assurance and methodology review pass.
8. **Separate FOMO-JEV swarm:** keep it separate from AURELIA as previously requested. It may produce research/coordination outputs only. It must not connect to the canonical capital plane or broker credentials; define its own repository, 8 role contracts, sandbox and acceptance evidence before considering integration.

## 6. AURELIA release gates (non-negotiable)

Current operational state remains **`CERTIFICATION_RESULT=NOT_READY`, `FINAL_EXECUTION_AUTHORIZATION=false`, `LIVE_EXECUTION=BLOCKED`**. Do not relax these because CI passes.

Required before any production authorization:
- Protected `main`, required checks, independent review, restricted production environment and verified bypass policy.
- Exact-commit full assurance with all artifacts retained and hashes checked.
- Protected Deriv authentication and account binding; verify-only lifecycle, fresh account/currency/balance and broker-minimum evidence.
- Recovery matrix and reconciliation/idempotency evidence; no real order is needed to claim a verify-only check.
- Strategy-specific prospective OOS, probability calibration/drift checks, and net expectancy after measured contract costs.
- Completed 3,600-second soak on the intended persistent production runtime, with monitoring and recovery evidence.
- Independent security review, deployment verification, rollback/kill-switch test, and explicit owner approval.
- All mandatory evidence present and valid. Any UNKNOWN or stale evidence blocks release.

## 7. What has and has not been completed

**Verified in this review:** four account-visible repositories returned by GitHub search; canonical repository and current README; ten registered agent roles and their task evidence paths; 367 external federation entries and mode counts; current PR backlog metadata and descriptions for the high-priority items; prior 12-source audit documents.

**Not verified and must not be represented as done:** clones or local execution of all repositories; completed SBOM/secret/license/CVE scans for all 367 sources; active provider connections or real agent heartbeats; persistent production host; protected GitHub rules and environment configuration after changes; authenticated Deriv lifecycle; prospective strategy qualification; 3,600-second soak; live production readiness.

The current environment does not provide an authorized connected development machine or verified persistent runtime. Do not fabricate execution evidence or attempt to bypass this limitation. Continue documentation and GitHub-hosted checks that are available, and leave host-dependent tasks explicitly blocked until a real authorized runner is connected.

## 8. Completion definition

A workstream is complete only when its acceptance criteria are met on a pinned commit, machine-readable evidence is retained, an independent reviewer signs off, unresolved findings are closed or explicitly accepted by the owner, and the result is reflected in the shared task ledger. A PR merge, CI green badge, repository registration, model response, or agent heartbeat alone is insufficient.



## 2026-10-17 external repository intake update

The new intake batch added 67 unique repositories from 69 URLs to the external-source registry (two duplicate URLs were de-duplicated). The registry now contains 367 entries: 173 `SANDBOX_ONLY`, 58 `TOOLCHAIN_ONLY`, 64 `RESEARCH_ONLY`, and 72 `REFERENCE_ONLY`. The batch report `docs/EXTERNAL_REPOSITORY_PORTFOLIO_TRIAGE_2026-10-17.md` records pinned revisions, license metadata, initial risk notes and proposed review ownership. The separate `docs/ODYSSEUS_EXTERNAL_REPOSITORY_ASSESSMENT_2026-10-17.md` records the Odysseus source triage. These reports do not claim isolated build or security scan evidence. The registry does not mean all entries have been cloned, built, or fully security-scanned.


## Additional source triage — Odysseus (2026-10-17)

The separately submitted `odysseus-dev/odysseus` workspace is registered as `SANDBOX_ONLY` at commit `9712a5400175f8beacb215cefed1dad6935627df`. It is a general self-hosted agent workspace with shell, files, MCP and memory capabilities, not a trading engine. README calls out `AUTH_ENABLED=true` and `LOCALHOST_BYPASS=false` outside local development; these must be independently tested. Repository reports AGPL-3.0-or-later. No install or deployment was performed. See [Odysseus source triage](ODYSSEUS_EXTERNAL_REPOSITORY_ASSESSMENT_2026-10-17.md).
