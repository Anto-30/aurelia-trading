# Roadmap Repository Intake and Agent Assignment
Date: 2026-10-10
Canonical repository: https://github.com/Anto-30/aurelia-trading
Target branch: `research/roadmap-repository-intake-2026-10-10`
Status: intake manifest only; no external repositories have been cloned or installed by this commit.

## Objective

Catalogue these nine user-supplied repositories, route them to the appropriate research and engineering roles, and define a safe path for using them across AURELIA, Claude Code, Grok, JEV and ChatGPT. These are primarily educational roadmaps and exercises, not drop-in trading software. Their value is skill development, onboarding, reference discovery and engineering practice; they must not be copied into the live execution path merely because they appear useful.

## Repository inventory and primary assignment

| # | Repository | Primary topic | Primary reviewer/agent | Secondary reviewers | Intended use |
|---:|---|---|---|---|---|
| 1 | https://github.com/nilbuild/developer-roadmap.git | Broad software-engineering roadmaps and topic references | ChatGPT — research synthesis | Claude Code — engineering relevance; Grok — stale/contradictory recommendations; JEV — evidence and source checks | General learning index; select only topics relevant to AURELIA's actual stack |
| 2 | https://github.com/mouredev/roadmap-retos-programacion.git | Programming logic and practice challenges | Claude Code — exercise selection | ChatGPT — curriculum mapping; JEV — reproducibility | Sandboxed coding exercises, fundamentals and test practice |
| 3 | https://github.com/milanm/DevOps-Roadmap.git | DevOps concepts, tooling and operational practices | Claude Code — CI/CD and operations review | JEV — operational controls; Grok — alternatives and trade-offs; ChatGPT — synthesis | Compare deployment, observability, incident response and delivery practices against the existing stack |
| 4 | https://github.com/MoienTajik/AspNetCore-Developer-Roadmap.git | ASP.NET Core/.NET | Claude Code — stack applicability | ChatGPT — classify as relevant/irrelevant; Grok — challenge adoption assumptions | Reference only unless a documented AURELIA component actually uses .NET; do not add a new runtime for its own sake |
| 5 | https://github.com/mrdbourke/machine-learning-roadmap.git | Machine-learning learning path | ChatGPT — research and curriculum mapping | JEV — experimental-method review; Grok — leakage/overfitting critique; Claude Code — implementation feasibility | ML foundations, evaluation and experiment-design references; no strategy qualification implied |
| 6 | https://github.com/skydoves/android-developer-roadmap.git | Android/Kotlin/mobile ecosystem | Claude Code — mobile engineering review | ChatGPT — applicability review | Optional mobile/field-operations reference; not a trading-engine dependency |
| 7 | https://github.com/ploi/roadmap.git | Hosting/deployment product roadmap (verify repository scope and licence on checkout) | Claude Code — infrastructure relevance | JEV — deployment/security review; Grok — vendor-lock-in challenge | Read-only comparison of hosting/deployment ideas; no production changes based solely on this repository |
| 8 | https://github.com/amitshekhariitbhu/android-developer-roadmap.git | Android application development | Claude Code — mobile engineering review | ChatGPT — applicability review; JEV — licence/provenance checks | Complementary/possibly overlapping Android reference; compare scope before treating as an independent source |
| 9 | https://github.com/s4kibs4mi/java-developer-roadmap.git | Java backend/software engineering | Claude Code — JVM/backend relevance | ChatGPT — applicability review; Grok — complexity and alternative-stack review; JEV — provenance/licence checks | Reference only unless the canonical stack has a justified JVM component |

Agent roles are proposals based on task type, not claims that those agent workspaces are currently connected. Every agent must report the exact repository commit and files reviewed, findings, actions taken, test evidence and unresolved concerns. Do not award contribution/reward points for unsupported claims.

## Shared agent responsibilities

- **ChatGPT (research coordinator and independent acceptance reviewer):** classify roadmap topics against current AURELIA needs; synthesize source-backed recommendations; maintain the contradiction and applicability register; review evidence independently. Do not claim to have installed code in other workspaces without a successful, observable tool result.
- **Claude Code (primary engineering implementer):** inspect the actual canonical checkout; turn approved engineering topics into small, testable improvements; run existing tests and relevant static/security checks; work on dedicated branches and submit reviewable PRs. Do not alter capital-plane behavior or merge its own unreviewed changes.
- **Grok (adversarial reviewer):** challenge stale content, unsupported best practices, overengineering, vendor bias, hidden assumptions and proposed changes that lack measurable benefit. Return counterexamples and references.
- **JEV (independent validation and operations reviewer):** check provenance/licences, dependency and supply-chain risks, test reproducibility, CI/deployment implications and whether evidence actually supports the claim. Keep independent findings separate from implementation claims.
- **AURELIA (consumer, not capital authority):** may consume approved, versioned learning notes or engineering proposals through the canonical research/documentation path. AURELIA's existing release authority, Risk Engine, Risk Warden, Execution Firewall, broker verification, idempotency, ledger reconciliation and kill switch remain authoritative. No roadmap repository or agent may authorize live trades.

## Tool and plugin routing

Use only tools that are actually connected and whose permissions fit the task. Suggested routing:
- GitHub connector: inspect default branches, commit SHAs, README, licence, release history, security policy, dependency manifests, and PR/issue context; record evidence. Keep changes in `Anto-30/aurelia-trading` on a dedicated branch.
- Repository-local shell/build environment (when connected): shallow-clone into an isolated research directory, pin commit SHAs, inspect manifests and run tests/scanners without credentials or production network access.
- Data-analytics skills: use only for quantitative dataset, metric, experiment or report work; roadmap content alone is not trading-performance evidence.
- Supabase/Vercel skills and connectors: use only if the existing AURELIA component under review actually uses those services and the task requires it. Do not provision or change production resources as part of repository intake.
- Security review: inspect licence, dependencies, install scripts, workflows, actions pinned by mutable tags, secrets access, telemetry/network behavior and provenance before running code.
- If an agent-specific workspace connector is unavailable, save the assignment in this canonical manifest and report synchronization as BLOCKED rather than implying the repo was copied there.

## Installation and acceptance workflow

1. Confirm each URL resolves to the intended repository; record owner/name, default branch, latest inspected commit SHA, archived/active state and last meaningful activity.
2. Read README, LICENSE, SECURITY policy, contribution rules and all install/build scripts before execution. Do not infer licence permissions from a README badge alone.
3. Clone only to an isolated research workspace; pin commits. Do not run untrusted install scripts with secrets, privileged access, broker access or access to production networks.
4. Classify each repo as `REFERENCE_ONLY`, `EXERCISE_SANDBOX`, `POTENTIAL_ENGINEERING_PATTERN`, `NOT_APPLICABLE`, or `BLOCKED_LICENSE_OR_SECURITY`.
5. For overlap, especially the two Android roadmaps and broad developer-roadmap resources, compare content and provenance before assigning distinct evidentiary weight.
6. Create a short learning/engineering note for any adopted idea: source commit and file/section, problem addressed, expected benefit, implementation location, tests, risks, rollback and reviewer.
7. Propose any actual AURELIA code change in a separate reviewed PR. Do not paste roadmap content wholesale or add a new language/framework without a justified requirement.
8. Confirm agent/workspace synchronization individually. A GitHub manifest being readable by an agent is not proof that the repo was installed into that agent's environment.

## AURELIA invariants

- One canonical system, one capital plane, one release authority and one evidence lineage.
- Research Plane and Capital Plane remain separated.
- Preserve all existing strategy registry entries and evidence, including S7, S6, S3, CRT and the existing scalping strategy.
- No roadmap repository is a trading strategy or proof of an edge.
- No production deployment, live order, credential change, live lock change or risk-gate weakening is authorized by this intake.
- Missing broker, hosting, data, out-of-sample, cost, soak or reconciliation evidence remains a blocker; do not relabel it as complete.
- Prefer no change over an unjustified dependency or architectural expansion.

## Current status and limitations

- `main` was inspected as the repository default branch and was not modified by this intake.
- This branch records the nine URLs, proposed assignments, tool-routing guidance and safety gates.
- **Not yet completed:** external clones; commit-pinned per-repository audit; licence/security verification; test runs; actual synchronization into Claude Code, Grok, JEV or any separate ChatGPT workspace; production integration.
- The repository connector can modify this canonical GitHub repo, but no connected local Desktop Commander device has been confirmed in this task. External agent workspaces are not assumed to be accessible.
- No quantitative strategy results or live-trading readiness conclusions follow from these educational resources.

## Required completion evidence

A follow-up audit must append a table with each repository's resolved default branch, exact commit SHA, licence and security status, checkout location, tests/scans run, assigned agent's evidence response, disposition and any approved PR. If a field cannot be verified, mark it `UNKNOWN` or `BLOCKED`; do not guess.
