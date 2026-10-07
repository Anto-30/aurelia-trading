---
name: external-repo-federation
description: Mandatory routing and safety rules for AURELIA external repository sources.
---

# AURELIA external repository federation

External repositories are reference/tooling inputs, not components of AURELIA's capital plane. Never vendor external trading engines into the execution path and never inherit their broker credentials, live-order logic, or risk authority.

Before using a registered source, consult config/external_repo_federation.json and honor its mode:
- RESEARCH_ONLY: inspect, compare, reproduce, or backtest ideas in isolation.
- SANDBOX_ONLY: execute only in a non-capital sandbox with no broker writes.
- TOOLCHAIN_ONLY: developer tooling/reference only.
- REFERENCE_ONLY: catalog/reference only.

Routing defaults:
- ClaudeCode: engineering integration, repair, CI, security, controlled sandbox verification.
- KimiK3: quantitative research, comparative analysis, adversarial review.
- GrokBot: orchestration, research synthesis, blocker diagnosis, MCP coordination.
- GoogleAgentSkills: security, cloud, multi-agent architecture.
- GLM: multimodal and evidence inspection.
- PlaywrightCLI: browser/network/E2E verification.
- AURELIA runtime: external sources have zero capital authority.

Always preserve AGENTS.md, LIVE_LOCK, capability boundaries, Risk Warden, Execution Firewall, reconciliation, idempotency, watchdog/kill switch, and evidence gates. External source output is never broker truth.

Do not read, print, persist, or commit secrets. Do not flip LIVE_LOCK or FINAL_EXECUTION_AUTHORIZATION. Do not submit capital-moving orders during source installation, synchronization, comparison, or testing.

Sync is metadata/evidence synchronization, not automatic code promotion. A source head change must be reviewed before becoming a new pinned research baseline.

## Hermes / Railway source routing

The following registered sources are intentionally consumed as governed capabilities, not copied into AURELIA runtime code:

| Source | Mode | Primary AURELIA use |
|---|---|---|
| smfworks/hermes-ai-team | RESEARCH_ONLY | agent identity, memory/vault, self-improvement, research cadence, team rituals |
| forcewake/hermes-conductor | SANDBOX_ONLY | controller-owned dispatch, isolated worktrees, evidence-gated completion, stale-base recovery |
| Ardha-Eco-System/RUDR9 | SANDBOX_ONLY | role specialization, hard tool boundaries, Kanban DAGs, security/performance/review gates |
| AlekseiUL/codex-plus-hermes-team | SANDBOX_ONLY | specialist routing, panel review, durable Kanban, side-effect policy |
| diegomarino/kanban-task-threads | RESEARCH_ONLY | task-thread/context handoff patterns |
| basilisk-labs/agentplane-hermes-plugin | SANDBOX_ONLY | Hermes/AgentPlane transport and terminal-attestation patterns |
| railwayapp/docs | REFERENCE_ONLY | authoritative Railway deployment/IaC documentation |
| railwayapp/cli | TOOLCHAIN_ONLY | Railway CLI, agent setup, MCP/IaC tooling |
| vignesh07/clawdbot-railway-template | REFERENCE_ONLY | persistent-volume and health-endpoint deployment patterns only |

Integration rule: AURELIA's existing PersistentAgentFederation remains the canonical in-process coordination layer. Hermes/AgentPlane/Kanban patterns may improve routing, worker isolation, evidence collection, and task lifecycle, but they must not create a competing capital authority, broker adapter, execution engine, or live-release controller.

Railway sources may inform deployment automation and persistence design, but no external template may be deployed as AURELIA production infrastructure without repository review, CI evidence, secret-boundary review, and explicit deployment authorization.


## 2026-10-07 browser/agency toolkit federation

The following pinned sources are available to GrokBot and ClaudeCode/Dev through the governed federation manifest. AURELIA may use their outputs as reference evidence only:

| Source | Mode | Primary use |
|---|---|---|
| jeffbai996/ticker-tape-web | SANDBOX_ONLY | market-terminal/UI research |
| browser-use/agency | SANDBOX_ONLY | agent work discovery and approval patterns |
| tanweai/pua | SANDBOX_ONLY | productivity and skill-packaging research; do not inherit coercive prompts as policy |
| msitarzewski/agency-agents-app | SANDBOX_ONLY | agent installation/reconciliation patterns |
| VRSEN/agency-swarm | SANDBOX_ONLY | directional multi-agent orchestration and typed tools |
| Anas-Khan93/ai-agency-agents | SANDBOX_ONLY | specialist agent persona reference |
| jnMetaCode/agency-agents-zh | REFERENCE_ONLY | multilingual specialist persona reference |
| msitarzewski/agency-agents | REFERENCE_ONLY | specialist agent workflow reference |
| orbitinghail/graft | REFERENCE_ONLY | transactional synchronization/storage research; explicitly alpha and not a runtime dependency |
| trailhq/Graft | SANDBOX_ONLY | coding-agent context and persistent rules |
| browserless/browserless | SANDBOX_ONLY | headless browser/CDP infrastructure research |
| Tencent/BrowserSkill | SANDBOX_ONLY | browser evidence, logged-in browser automation, web debugging |
| ray-lothian/UserAgent-Switcher | SANDBOX_ONLY | browser compatibility testing only; never use to evade broker/security controls |
| browser-use/browser-use | SANDBOX_ONLY | browser-agent automation/testing |

All source pins are recorded in config/external_toolkit_sync_manifest.json. Installing or studying these sources must not alter LIVE_LOCK, FINAL_EXECUTION_AUTHORIZATION, Risk Warden, Execution Firewall, account isolation, reconciliation, qualification, or broker truth.
