# AURELIA Operational Handoff — 2026-10-03

## Purpose

This document records the current engineering handoff for the existing AURELIA architecture. It is a source-of-truth navigation aid, not a live-capital authorization.

## Current repository state

- Repository: `Anto-30/aurelia-trading`
- Canonical branch: `main`
- Default branch: `main`
- Current runtime entry point: `runtime/main.py`
- Readiness orchestrator: `runtime/ops/readiness_orchestrator.py`
- Capital plane: `capital/capital_plane.py`
- Capital execution authority: `runtime/broker/executor.py`
- Modern Deriv session manager: `runtime/adapters/session_manager.py`
- Modern Deriv OTP/session implementation: `runtime/adapters/deriv_session.py`
- Deriv transport: `runtime/adapters/deriv_ws.py`
- Walk-forward validation: `runtime/validation/walk_forward.py`
- Live-release control: `config/LIVE_LOCK.yaml`

## Current release state

The repository remains fail-closed:

`FINAL_EXECUTION_AUTHORIZATION=false`

`LIVE_EXECUTION=BLOCKED`

`config/LIVE_LOCK.yaml` remains the controlling release artifact and currently keeps the capital plane in verification-only mode.

## Deriv state

The latest external verification report supplied to the engineering process established the modern REST + OTP WebSocket path and a fresh real-account balance snapshot. This handoff records the architectural result without copying credentials or OTPs into GitHub.

The repository implementation uses `api.derivws.com` as the canonical Options API host. Legacy `ws.derivws.com` endpoints are diagnostic-only.

## Railway state

The existing Railway project is:

`AURELIA-Production-Worker`

The production environment exists, but the connected Railway control plane currently reports no service/deployment. A deployment attempt is blocked by the Railway account plan/trial state. No substitute worker or duplicate trading engine is to be created.

## Remaining qualification work

The repository must still retain its existing requirements for:

- prospective multi-day OOS
- calibrated and current probability evidence
- net execution economics
- 3600-second adversarial runtime soak
- deployment lineage and runtime health
- complete capital-control conjunction

No live order is authorized merely because Deriv authentication succeeds.

## Capital/stake policy

Starting stake reference:

`$1.00`

The stake is dynamic rather than fixed. Verified balance is an affordability ceiling, not permission to risk the full account. Risk Warden, LivePolicy, Capital Plane, Execution Firewall, exposure controls, and release gating remain sovereign.
