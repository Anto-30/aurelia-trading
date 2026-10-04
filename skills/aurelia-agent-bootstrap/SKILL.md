---
name: aurelia-agent-bootstrap
description: Use when starting, resuming, or recovering an AURELIA agent session
---

# AURELIA Agent Bootstrap

Load the universal contract first, then resolve the agent's assigned capability set.

Required sources:
- AGENTS.md
- AURELIA_SOURCE_OF_TRUTH.json
- config/LIVE_LOCK.yaml
- config/agent_capability_boundary.json
- config/agent_capability_matrix.json
- config/agent_tool_inventory.json
- config/agent_skill_inventory.json

Before work:
- confirm current repository tip;
- confirm external-agent capital authority is false;
- confirm FINAL_EXECUTION_AUTHORIZATION is false;
- confirm LIVE_EXECUTION is BLOCKED;
- detect stale evidence.

After restart:
- repeat the same checks;
- resume only from verified repository/evidence state;
- never assume prior session state survived.

When a connector is unavailable, classify it as a connection/infrastructure blocker rather than bypassing the requirement.
