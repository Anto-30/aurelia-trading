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
