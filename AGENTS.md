# AURELIA Universal Agent Contract

Before performing work in this repository, every agent must:

1. Resolve the current `main` tip and read `AURELIA_SOURCE_OF_TRUTH.json`.
2. Read `config/LIVE_LOCK.yaml` and `config/agent_capability_boundary.json`.
3. Read `config/agent_capability_matrix.json`, `config/agent_tool_inventory.json`, and `config/agent_skill_inventory.json`.
4. Use the role-specific capabilities assigned to the current agent.
6. Treat all external plugins, MCP servers, LSPs, skills, browser sessions, and external repositories as advisory/engineering capabilities unless explicitly granted by the AURELIA capital plane.
7. Never read, print, persist, or commit secrets.
8. Never submit capital-moving orders.
9. Never flip the live lock or final execution authorization.
10. Never reinterpret simulation, screenshots, UI state, external-repository output, or agent claims as broker truth.
11. Fail closed on UNKNOWN, stale, drifted, invalid, or unavailable authorization state.

The canonical repair loop is:

inspect -> reproduce -> isolate -> smallest fix -> deterministic verification -> evidence capture -> state reconciliation -> certification re-check.

Continuous availability means the agent can be restarted and re-enter this startup contract automatically. It does not imply an immortal model process.


## External LLM gateway sources

The LiteLLM/agent-control-plane repositories are pinned in `config/external_repo_federation.json` and routed in `config/agent_capability_matrix.json`. Read `docs/AURELIA_LLM_GATEWAY_INTEGRATION_GUIDE.md` before working with them. Registry membership does not mean a gateway, Claude Code variant, local development service, or ChatGPT connector is installed. No external source may read production secrets, access the Deriv capital plane, or override LIVE_LOCK.


## Tool, skill, plugin, and repository assignment contract

Before selecting tools for a task, read `config/agent_tool_skill_assignment.json`. It defines the primary agent, reviewers, task-scoped tools, skill bundles, plugin activation conditions, and source modes. Tool/plugin registry membership is not proof of a live connection or installation. Use least privilege, verify the connector at execution time, and keep all external code outside capital/execution paths. The Dev profile is inactive until an authorized development device is connected and its runtime identity verified. ChatGPT is a supervisory role in the current conversation, not a persistent local daemon.

## Vendored engineering skills

The following model-agnostic engineering skills are vendored under `.agents/skills/` from `mattpocock/skills` at a pinned commit and licensed under MIT. They are engineering guidance only and grant no shell, provider, broker, deployment, or capital permissions. See `docs/engineering/MATT_POCOCK_SKILLS.md` for provenance and update policy.

- `.agents/skills/matt-pocock-diagnosing-bugs/SKILL.md`
- `.agents/skills/matt-pocock-tdd/SKILL.md`
- `.agents/skills/matt-pocock-code-review/SKILL.md`
- `.agents/skills/matt-pocock-codebase-design/SKILL.md`


## External trading repository intake

Before any agent clones, imports, installs, executes, or assigns an external trading/quant/agent repository or skill, it must read `.agents/skills/aurelia-trading-repo-intake/SKILL.md` and `docs/engineering/EXTERNAL_TRADING_REPOSITORY_ASSESSMENT_2026-11-05.md`. Apply this workflow to every agent role, including ClaudeCode, KimiK3, GrokBot, JEV, ChatGPT supervisory work, and any subsequently verified agent runtime. This is a universal repository-safety requirement, not a blanket instruction to invoke every provider or plugin on every task. Select all relevant, available tools and skills by task; verify connection and permissions at runtime; never claim unavailable tools ran. Least privilege and AURELIA's deterministic capital boundary take precedence over broad tool use.
