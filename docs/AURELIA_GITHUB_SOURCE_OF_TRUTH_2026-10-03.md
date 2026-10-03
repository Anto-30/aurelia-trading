# AURELIA GitHub Source-of-Truth Audit — 2026-10-03

## Purpose

This document defines the GitHub-side source-of-truth contract for the current AURELIA implementation.

## Canonical repository

- Repository: `Anto-30/aurelia-trading`
- Canonical branch: `main`
- Default branch: `main`
- Live release control: `config/LIVE_LOCK.yaml`
- Runtime entry point: `runtime/main.py`
- Readiness orchestrator: `runtime/ops/readiness_orchestrator.py`

## Required discovery path

`README.md`
→ `AURELIA_REPOSITORY_MAP.md`
→ `AURELIA_SOURCE_OF_TRUTH.json`
→ runtime / capital / execution
→ tests
→ evidence / documentation
→ deployment configuration

The paths above are required to remain directly browsable from `main`.

## Current implementation anchors

### Capital and execution

- `capital/capital_plane.py`
- `runtime/broker/executor.py`
- `runtime/broker/factory.py`
- `execution/deriv.py`

### Deriv

- `runtime/adapters/deriv_session.py`
- `runtime/adapters/session_manager.py`
- `runtime/adapters/deriv_adapter.py`
- `runtime/adapters/deriv_ws.py`
- `runtime/adapters/deriv_lifecycle.py`

Canonical modern Options API:

- REST: `https://api.derivws.com/trading/v1/options`
- Authenticated WS host: `api.derivws.com`
- Authenticated WS path: `/trading/v1/options/ws/{real|demo}`

Legacy `ws.derivws.com` / Binary WS v3 is diagnostic-only and must not be an executable production fallback.

### Controls

- `runtime/core/authority.py`
- `runtime/core/capabilities.py`
- `runtime/core/exposure.py`
- `runtime/core/idempotency.py`
- `runtime/core/fencing.py`
- `runtime/core/reconcile.py`
- `runtime/core/recovery.py`
- `runtime/core/release_gate.py`
- `runtime/core/health.py`
- `runtime/core/supervisor.py`
- `runtime/security/secrets.py`

### Validation

- `runtime/validation/walk_forward.py`
- `runtime/validation/probability.py`
- `runtime/validation/decision_replay.py`
- `runtime/strategy/governance.py`
- `assurance/adversarial_matrix.py`
- `assurance/soak_protocol.py`

### Deployment

- `railway.toml`
- `.github/workflows/railway-deploy.yml`
- `.github/workflows/deriv-session-verification.yml`
- `.github/workflows/aurelia-assurance.yml`

## Branch and history policy

`main` is authoritative for the current implementation.

Historical branches, archives, and old releases are non-authoritative unless explicitly promoted through the normal reviewed Git workflow.

Do not reconstruct historical implementation from documentation when source is unavailable.

Do not allow two competing execution engines to become authoritative.

## Security contract

Never commit or log:

- Deriv PATs
- OAuth access/refresh tokens
- OTP values
- authenticated WebSocket URLs containing credentials
- Railway tokens
- private keys
- passwords
- production secret values

Local secret files and runtime-generated secret-bearing evidence must remain outside source control.

## Operational state contract

GitHub source inspection proves repository state only.

It does not prove:

- a Railway worker is currently deployed
- a live Deriv session is currently established
- a fresh broker balance exists at runtime
- strategy live eligibility
- calibration
- net economics
- 3,600-second soak completion
- live capital authorization

Those require contemporaneous evidence from the relevant environment.

## Current external blocker known at audit time

The existing Railway project is reachable through the connected Railway control plane, but it currently contains no production service/deployment and deployment creation is rejected because the Railway trial has expired and requires a plan.

No substitute worker or duplicate execution engine is authorized.

## Capital authorization

The repository currently keeps:

`FINAL_EXECUTION_AUTHORIZATION = false`

`LIVE_EXECUTION = BLOCKED`

`capital_plane_mode = VERIFY_ONLY`

GitHub source visibility or repository write access must never grant capital authority.

## Verification

The repository includes source-of-truth and modern-Deriv regression tests. The current main branch should be re-read after every significant merge so the effective source-of-truth is always the remote `main` tip, not a stale local checkout.
