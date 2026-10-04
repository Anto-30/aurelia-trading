# AURELIA Current Operational State — 2026-10-04

This document records the currently verified state of the existing AURELIA implementation. It is not a live-capital authorization.

## Current source

- Repository: `Anto-30/aurelia-trading`
- Canonical branch: `main`
- Current certified engineering tip at the time of this report: `3389e630c9de05f14a05763a6456ad698aca7f81`
- Live-release control: `config/LIVE_LOCK.yaml`

## Verified engineering evidence

- Assurance run `37161897822`: success for the current tip.
- Non-production 3,600-second control-path soak run `37161897786`: success.
- Soak evidence classification: `SIMULATION_VERIFIED`.
- Soak duration: 3,601 seconds.
- Health checks: 706.
- Controlled restarts: 3.
- Health-check failures: 0.
- Runtime image identity: `sha256:690bf3b41f130cccd301a9ec3b07c00742f2b5a8dd0057b6bc8a9cd8c4bc3796`.
- Capital remained protected throughout the evidence run.

## Broker and infrastructure

- Modern Deriv REST/OTP WebSocket implementation: present and code-verified.
- Authenticated Deriv runtime session: not independently executed in the current environment because authorized secrets are unavailable.
- Real broker transaction/fill/reconciliation: not executed.
- Railway production worker: not deployed; the connected Railway account requires a plan.
- Production worker soak: not executed.

## Strategy qualification

- Live strategy eligibility: false.
- Prospective multi-day OOS: incomplete.
- Probability calibration/drift evidence: incomplete.
- Net execution economics: incomplete.

## Capital state

`FINAL_EXECUTION_AUTHORIZATION=false`

`LIVE_EXECUTION=BLOCKED`

`capital_plane_mode=VERIFY_ONLY`

`LIVE_ORDERS=0`

## Evidence interpretation

The 3,600-second soak is simulation-class evidence only. It does not establish authenticated broker access, a real transaction lifecycle, production infrastructure, production soak, strategy qualification, or live authorization.

## Federated engineering layer

Claude Code, Kimi K3/Kimi Code, Grok Bot, Google Agent Skills, GLM Skills, and Playwright CLI are registered as research/engineering capabilities in:

`config/agent_skill_federation.json`

Their shared authority boundary is:

`config/agent_capability_boundary.json`

No external agent or skill is permitted to move capital or modify the live-release lock.
