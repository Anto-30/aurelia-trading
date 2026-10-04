---
name: context-mode
description: MANDATORY routing rules for AURELIA engineering sessions using context-mode.
---

# AURELIA context-mode integration

context-mode is an engineering/context-management capability only. It has zero capital authority and must never bypass AURELIA controls.

For data-heavy analysis, prefer context-mode sandbox/index/search operations so raw output stays out of model context:
- ctx_batch_execute for batched commands and queries.
- ctx_execute for programmatic analysis.
- ctx_execute_file for large local files.
- ctx_fetch_and_index for web content.
- ctx_index and ctx_search for persistent indexed knowledge.
- ctx_stats and ctx_doctor for diagnostics.

## AURELIA safety boundary

context-mode does NOT grant capital authority, broker authority, live execution authority, permission to read or persist secrets, permission to change LIVE_LOCK, or permission to change FINAL_EXECUTION_AUTHORIZATION.

All work remains subject to AGENTS.md, LIVE_LOCK, capability boundaries, Risk Warden, Execution Firewall, reconciliation, and evidence gates.

Indexed context, screenshots, cached tool output, model claims, and context-mode session memory are not broker truth. Broker-confirmed evidence remains authoritative for authenticated capital state.

## Installation

AURELIA pins the integration contract to context-mode v1.0.169.

    npm install -g context-mode@1.0.169

Then restart the agent session and verify:

    context-mode doctor

For GitHub Copilot CLI, the upstream supported plugin bundle is:

    copilot plugin install mksglu/context-mode:configs/copilot-cli

Source: https://github.com/mksglu/context-mode
