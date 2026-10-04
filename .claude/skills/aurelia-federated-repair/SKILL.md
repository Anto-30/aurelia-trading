---
name: aurelia-federated-repair
description: Use when AURELIA needs cross-agent diagnosis, certification repair, CI/evidence reconciliation, browser verification, security review, or integration of external agent skills/plugins. Coordinate Claude Code, Kimi K3, Grok, Google Agent Skills, GLM, and Playwright concepts through one fail-closed workflow.
version: 1.0.0
---

# AURELIA Federated Repair

## Objective

Repair the existing AURELIA architecture, not replace it and not create a second trading engine.

The federation is an engineering/research capability layer. It has zero capital authority.

## Required sequence

1. Resolve the canonical repository tip from `main`.
2. Read `AURELIA_SOURCE_OF_TRUTH.json`, `config/LIVE_LOCK.yaml`, readiness state, current evidence, and open P0 issues.
3. Separate facts into code-path, assurance, simulation, authenticated-broker, transaction, reconciliation, infrastructure, production-soak, and live-authorization classes.
4. Identify stale metadata and contradictions before changing trading logic.
5. Decompose the defect:
   - Claude Code: implementation and test repair.
   - Kimi K3: parallel analysis, competing hypotheses, and cross-checking.
   - Grok: orchestration, ecosystem research, blocker diagnosis, and skill/registry synchronization.
   - Google Agent Skills: multi-agent security and deployment architecture review.
   - GLM: multimodal/document/table inspection when evidence is visual or document-heavy.
   - Playwright CLI: browser/UI, authenticated-session, network, tracing, and E2E verification where a reachable application exists.
6. Apply the smallest targeted repair to the existing architecture.
7. Run deterministic tests and assurance checks.
8. Re-run only the necessary runtime evidence and retain exact source/runtime identity.
9. Reconcile operational-state documents with actual evidence.
10. Re-check all capital invariants.
11. Never upgrade evidence class without the evidence required for that class.

## Evidence rules

- `SIMULATION_VERIFIED` never means broker verified.
- `AUTHENTICATED_BROKER_VERIFIED` never means a real transaction happened.
- `TRANSACTION_LIFECYCLE_VERIFIED` never means production-ready.
- `PRODUCTION_READY` never means live authorization.
- Unknown, stale, uncalibrated, drifted, or invalid evidence is fail-closed.

## Tool and plugin trust

Prefer official upstream sources and pin them to immutable commits in `config/agent_skill_federation.json`.

Community catalogs are discovery-only until independently reviewed.

Do not load external hooks/MCP/LSP components with production privileges.

## Capital boundary

Never:
- flip `config/LIVE_LOCK.yaml`;
- set `FINAL_EXECUTION_AUTHORIZATION=true`;
- submit live or demo capital-moving orders as part of skill installation;
- read or print secrets;
- treat an agent recommendation as authorization;
- bypass Risk Warden, Capital Plane Gate, Execution Firewall, Account Isolation, idempotency, reconciliation, or UNKNOWN handling.

## Completion criterion

A repair is complete only when the exact defect is reproduced or its absence is demonstrated, the targeted fix is test-backed, evidence lineage is preserved, stale state is corrected, and all unrelated certification gates remain unchanged.
