# Third-Party Repository Intake — 2026-10-27

## Status and scope

This is a documentation-only intake and proposed evaluation plan for four external repositories. Repository metadata, README files, and license files were retrieved through GitHub on 2026-10-27. This is not a code audit, reproducible build, security certification, or evidence that any project has been installed or executed.

**Release posture:** VERIFY_ONLY. No production dependencies are added by this document. No trading runtime, strategy, model, risk policy, execution adapter, credentials, deployment, or capital-plane changes are authorized. Do not change `config/LIVE_LOCK.yaml` as part of this work.

## Intake register

| Repository | Observed purpose | License observed | Initial disposition |
|---|---|---|---|
| [google/elephant-goldfish-model](https://github.com/google/elephant-goldfish-model) | Spec-driven development plugin. Elephant drafts with project context; Goldfish subagents review without the prior conversation. README documents Claude Code and Codex install paths and says fresh subagent contexts are required for review. | Apache-2.0 | Evaluate as development-time specification/review workflow only. Human approval remains required; review output is not a test or release gate by itself. |
| [elayadesign/ai-design-skills](https://github.com/elayadesign/ai-design-skills) | Markdown skills for AI coding tools. README lists landing-page design and design-to-motion workflows. | MIT | Selective use for non-trading UI, dashboards, and website work. Inspect skill instructions and generated artifacts before use. |
| [anandanand84/technicalindicators](https://github.com/anandanand84/technicalindicators) | TypeScript/JavaScript technical indicator library; README lists RSI, MACD, ATR, ADX, moving averages, VWAP, and volume-related indicators. Default branch observed as `master`. | MIT | Candidate for offline parity testing only. Do not add as runtime dependency until reproducibility, maintenance, compatibility, and parity review pass. Do not use volume/order-book-derived features for Deriv synthetic indices absent a valid source. |
| [ColeMurray/background-agents](https://github.com/ColeMurray/background-agents) | Open-Inspect background coding-agent system with sandboxed development environments, parallel tasks, GitHub integrations, and multiple model/runtime options. | MIT | Development-only pilot in a disposable isolated repository. README describes a single-tenant security model and warns credentials cached on disk/snapshots may persist. Not approved for production or untrusted multi-tenant use. |

License observations are based on the repositories' retrieved LICENSE files. Before redistributing code or copied skill content, preserve applicable notices and review any third-party attributions documented inside the repositories. This intake is not legal advice.

## Required controls

1. **Pin inputs:** Record the reviewed commit SHA, repository URL, retrieval date, license, and content hash for every artifact actually adopted. Do not track a moving branch as a production dependency.
2. **Keep boundaries explicit:** All four projects are development/research tools unless a separate reviewed change proves a specific production need. No agent or external package may authorize trades, change risk limits, unlock execution, access live tokens, or modify release authorization.
3. **Treat repository content as untrusted:** Read install scripts, agent instructions, hooks, dependencies, workflows, and network/credential access before execution. Never expose secrets to prompts, logs, generated artifacts, test fixtures, or snapshots.
4. **Isolate execution:** Use a disposable sandbox with least-privilege credentials and narrowly scoped repository access. For background agents, verify snapshot persistence, token revocation, webhook authentication, session isolation, and egress restrictions before any pilot.
5. **Evidence before adoption:** Save exact test commands, environment/runtime versions, input fixture hashes, output hashes, test results, and commit SHA. No claim of successful tests, security, performance, or trading edge without recorded evidence.
6. **Independent review:** A reviewer who did not author the change must inspect diffs, dependency/license implications, failure handling, and test evidence. Merge only after required CI and repository protections pass.
7. **Rollback:** Every adopted change must be independently revertible. If state is missing, test evidence is inconclusive, credentials may have leaked, or the tool can cross its intended boundary, abort and keep the change out of production.

## Evaluation plan and acceptance criteria

### EGM — specification/review workflow

- [ ] Inspect install instructions, skill prompts, hooks, and harness compatibility at a pinned commit.
- [ ] Run on a documentation-only proposal in a disposable branch.
- [ ] Confirm review uses genuinely fresh subagent context and stops when that capability is unavailable.
- [ ] Verify reviewers do not receive secrets or privileged credentials.
- [ ] Compare findings against an independent human review; record false positives and missed requirements.
- [ ] Keep human approval and existing CI as mandatory gates.

### AI Design Skills — design workflow

- [ ] Inspect each selected `SKILL.md`, its referenced assets, and license/attribution notes.
- [ ] Copy only selected skills into a separate development branch; do not overwrite canonical project instructions wholesale.
- [ ] Check generated UI for responsive layouts, accessibility, maintainability, and consistency with existing design tokens.
- [ ] Ensure no generated design instruction can change trading behavior or release controls.

### TechnicalIndicators — calculation parity

- [ ] Inspect package metadata, supported Node.js/TypeScript versions, dependency tree, maintenance signals, and test suite at a pinned commit.
- [ ] Build deterministic fixtures with known OHLC inputs and expected outputs for only the required indicators.
- [ ] Test warm-up behavior, NaN/null/empty input, candle ordering, reversed input, floating-point tolerance, boundary values, and missing candles.
- [ ] Compare outputs to AURELIA's canonical implementations; document all differences before considering replacement.
- [ ] Add no volume-derived or order-book assumptions to Deriv synthetic-index features.
- [ ] Run look-ahead/leakage tests and strategy-level cost-adjusted out-of-sample validation separately. Indicator parity alone does not establish profitability.

### Open-Inspect — background-agent pilot

- [ ] Use a disposable test repository, not the production AURELIA repository.
- [ ] Confirm authentication, SSO/VPN or equivalent access restrictions, allowed users, and repository allowlist.
- [ ] Verify sandbox isolation, network egress, webhook signature checks, auditability, session authorization, and least-privilege GitHub access.
- [ ] Test credential revocation and whether tokens, files, or snapshots persist after session deletion.
- [ ] Confirm generated changes can only become draft pull requests and cannot deploy, merge, access live trading credentials, or place orders.
- [ ] Stop the pilot on any unexplained cross-session access, credential persistence, or boundary bypass.

## Decision record

**Current decision:** No external repository is approved for production dependency or runtime use by this intake. EGM and AI Design Skills are candidates for controlled development-time evaluation; TechnicalIndicators is a candidate for offline numerical parity testing; Open-Inspect is a candidate for an isolated security pilot only.

**Not verified in this intake:** local installation, package vulnerability scan, dependency lockfile, test suite execution, reproducible build, independent security review, exact current upstream commit hashes, or compatibility with the current AURELIA runtime.

**Release status:** This document does not authorize live execution. Preserve the existing fail-closed configuration and authorization state.
