# ADR-001: Map the Layer-9 research programme onto existing AURELIA components

- **Status:** Accepted as a research/architecture decision by ATOS v2.0 owner delegation
- **Date:** 2026-11-11
- **Scope:** Research architecture and documentation only
- **Implementation authority:** `AURELIA_REPOSITORY_MAP.md` and `AURELIA_SOURCE_OF_TRUTH.json` on canonical `main`

## Context

ATOS v2.0 introduces a logical L0-L10 responsibility model to organize the Layer-9 research programme. AURELIA already has a canonical production architecture and named control components. Creating duplicate production layers would create competing authorities, duplicate state, and ambiguity around execution and risk ownership.

The master specification is an authority for Layer-9 research only. It does not supersede the repository map, source-of-truth metadata, the Layer-6 risk authority, or `config/LIVE_LOCK.yaml`.

## Decision

Use the following mapping as a research responsibility map. It is not an instruction to create new production layers or move current production components.

| Logical responsibility | Existing AURELIA implementation / research boundary |
|---|---|
| L0 Governance and security | `runtime/security/`, `assurance/`, `config/` policies |
| L1 Data | Research-side licensed ingestion and ephemeral feed adapters |
| L2 Features and regimes | Research-side feature and regime modules |
| L3 Strategy research | `research/` with promotion governance in `runtime/strategy/governance.py` |
| L4 Portfolio/allocation research | Research-side portfolio and exposure studies; no capital authority |
| L5 Execution semantics | `execution/`, `runtime/broker/`, `runtime/adapters/` only as offline simulation/replay contracts under this specification |
| L6 Risk Authority | `capital/capital_plane.py`, `runtime/core/` authority/exposure/fencing/reconciliation/release-gate controls, and `config/LIVE_LOCK.yaml` |
| L7 Monitoring and operations | `runtime/core/health.py`, `runtime/core/supervisor.py`, `runtime/ops/` |
| L8 Journal and reporting | `reports/` and the existing `runtime/core/ledger.py` contract |
| L9 Research engine | `research/` and `runtime/validation/` |
| L10 AI orchestration | Research-only orchestration with read-only result access |

L6 remains the sole deterministic Risk Authority. The single capital executor remains `runtime/broker/executor.py`. No research service, AI agent, LLM, external repository, or proposed logical layer receives order, capital, release, secret, or risk authority.

## Alternatives considered

1. **Implement L0-L10 as new production services:** rejected. It duplicates existing architecture and risks multiple control authorities.
2. **Replace the canonical repository map with the research-layer model:** rejected. The main-branch repository map and source-of-truth metadata remain implementation authority.
3. **Leave the research programme unmapped:** rejected. A mapping improves traceability while preserving current production ownership.

## Consequences

- New research modules must live in the research plane unless a separate, numbered ADR explicitly changes the boundary.
- Any future production architecture change requires its own ADR, review, and owner ratification.
- No change to capital, order execution, broker authentication, risk state, release authority, or `LIVE_LOCK` is authorized by this ADR.
- Historical branches are not production architecture authority.

## Ratification

This mapping is accepted for the Layer-9 research programme under the owner-delegated ATOS v2.0 specification effective 2026-11-11. It does not authorize production implementation or live execution.
