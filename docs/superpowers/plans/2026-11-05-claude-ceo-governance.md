# Claude CEO Governance Implementation Plan

> **For agentic workers:** Use the repository's role-scoped skills and execute each task on the isolated governance branch. Do not claim an agent ran unless its worker lease and task evidence exist.

**Goal:** Make ClaudeCode AURELIA's primary executive orchestrator while preserving the deterministic capital-control boundary and independent review.

**Architecture:** Update the canonical agent assignment, capability matrix/boundary, and repository routing consistently. Add a durable charter and regression tests that reject capital authority, live-lock mutation, and false claims of external runtime connectivity.

**Tech Stack:** JSON policy configuration, Markdown governance documentation, Python `unittest`, GitHub Actions.

**Spec:** `docs/AURELIA_CLAUDE_CEO_CHARTER_2026-11-05.md`

## Global Constraints

- `ClaudeCode` remains a non-capital agent and cannot mutate `LIVE_LOCK`.
- `AURELIA` remains the sole deterministic capital-control plane.
- GrokBot remains a specialist orchestration/adversarial-review support agent.
- Agent roster membership never proves live worker connectivity.
- OpenClaw, Cursor IDE, Codex, DeepSeek Harness, and Hermes remain unconnected until verified.
- Production secrets, broker actions, and live-release gates are out of scope.
- All changes remain on `governance/claude-ceo-orchestrator-2026-11-05` and are submitted as a draft PR.

## Review Focus

- Configuration drift between assignment, routing, capability, and boundary registries.
- Accidental promotion of CEO authority into capital, secret, live-lock, or deployment authority.
- Agent names incorrectly reported as connected workers.
- Loss of independent QA/release review.
- Contradictions with the existing validator and source-of-truth contract.

## Tasks

- [ ] Add regression tests for the executive designation and forbidden permissions.
- [ ] Update the canonical assignment and task routes.
- [ ] Align repository routing, capability matrix, and capability boundary.
- [ ] Add the executive charter and universal agent instruction.
- [ ] Extend the existing assignment validator.
- [ ] Verify via available CI; report unrun checks and missing agent workers explicitly.
