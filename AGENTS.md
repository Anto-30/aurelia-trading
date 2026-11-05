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

## Executive agent governance

`ClaudeCode` is the primary executive coordinator (AURELIA CEO) and principal engineering lead for bounded non-capital work. It may prioritize work, decompose initiatives, delegate to registered specialists, coordinate reviews, and track delivery evidence under the task-scoped permissions in `config/agent_tool_skill_assignment.json`.

Delegation through the persistent federation requires a registered agent, a verified active worker lease, a task claim, and terminal evidence before completion is reported. A profile, queued message, or model name is not proof of a connected or executing worker. If a runtime is unavailable, mark it `NOT_CONNECTED` or `PENDING_UNCLAIMED`.

The CEO designation does not grant capital authority, broker-order authority, production-secret access, live-lock mutation, final execution authorization, release-gate bypass, or production-deployment authority. `AURELIA` remains the deterministic capital-control plane. Independent review and the fail-closed release contract remain mandatory.
