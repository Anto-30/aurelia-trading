# AURELIA Repository Map

This is the browsable map of the current AURELIA implementation on `main`.

## Source of truth

- Repository: `Anto-30/aurelia-trading`
- Branch: `main`
- Live release control: `config/LIVE_LOCK.yaml`
- Runtime configuration: `config/runtime.yaml`
- Runtime entry point: `runtime/main.py`
- Readiness orchestrator: `runtime/ops/readiness_orchestrator.py`

## Capital and execution

- Capital plane: `capital/capital_plane.py`
- Single capital executor: `runtime/broker/executor.py`
- Capital-plane factory: `runtime/broker/factory.py`
- Deriv execution facade: `execution/deriv.py`
- Deriv adapter: `runtime/adapters/deriv_adapter.py`
- Deriv OTP/session API: `runtime/adapters/deriv_session.py`
- Session manager: `runtime/adapters/session_manager.py`
- WebSocket transport: `runtime/adapters/deriv_ws.py`
- Lifecycle: `runtime/adapters/deriv_lifecycle.py`

## Controls

- Authorization: `runtime/core/authority.py`
- Capability boundaries: `runtime/core/capabilities.py`
- Exposure: `runtime/core/exposure.py`
- Idempotency: `runtime/core/idempotency.py`
- Fencing: `runtime/core/fencing.py`
- Reconciliation: `runtime/core/reconcile.py`
- Recovery: `runtime/core/recovery.py`
- Release gate: `runtime/core/release_gate.py`
- Health/watchdog: `runtime/core/health.py`, `runtime/core/supervisor.py`
- Secret handling: `runtime/security/secrets.py`
- Test ledger contract: `runtime/core/ledger.py`

## Research and validation

- Walk-forward/OOS: `runtime/validation/walk_forward.py`
- Probability/calibration: `runtime/validation/probability.py`
- Decision replay: `runtime/validation/decision_replay.py`
- Strategy governance: `runtime/strategy/governance.py`
- Prospective OOS archiver: `research/r100_prospective_oos_archiver.py`
- Assurance hardening: `assurance/aurelia_hardening.py`
- Assurance invariants: `assurance/aurelia_invariants.py`
- Adversarial matrix: `assurance/adversarial_matrix.py`
- Soak contract: `assurance/soak_protocol.py`

## Operational documentation

- Modern Deriv path: `docs/AURELIA_MODERN_DERIV_PATH_2026-10-03.md`
- Stake policy: `docs/AURELIA_STAKE_POLICY_2026-10-03.md`
- Runtime baseline: `docs/AURELIA_RUNTIME_BASELINE_2026-10-03.md`
- Deployment/auth workflows: `.github/workflows/`

Historical archives and old branches are not the current source of truth.
