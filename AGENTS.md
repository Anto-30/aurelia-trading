# AURELIA Universal Agent Contract

Before performing work in this repository, every agent must:

1. Resolve the current `main` tip and read `AURELIA_SOURCE_OF_TRUTH.json`.
2. Read `config/LIVE_LOCK.yaml` and `config/agent_capability_boundary.json`.
3. Read `config/agent_capability_matrix.json`, `config/agent_tool_inventory.json`, and `config/agent_skill_inventory.json`.
4. Use the role-specific capabilities assigned to the current agent.
5. Treat all external plugins, MCP servers, LSPs, skills, and browser sessions as advisory/engineering capabilities unless explicitly granted by the AURELIA capital plane.
6. Never read, print, persist, or commit secrets.
7. Never submit capital-moving orders.
8. Never flip the live lock or final execution authorization.
9. Never reinterpret simulation, screenshots, UI state, or agent claims as broker truth.
10. Fail closed on UNKNOWN, stale, drifted, invalid, or unavailable authorization state.

The canonical repair loop is:

inspect -> reproduce -> isolate -> smallest fix -> deterministic verification -> evidence capture -> state reconciliation -> certification re-check.

Continuous availability means the agent can be restarted and re-enter this startup contract automatically. It does not imply an immortal model process.
