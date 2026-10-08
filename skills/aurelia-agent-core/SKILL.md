---
name: aurelia-agent-core
description: Safe common operating rules for every AURELIA agent. Use on every task touching the repository, deployment, evidence, research, or agent tooling.
---
# AURELIA Agent Core
1. Preserve the existing AURELIA architecture; do not create a second trading engine.
2. Treat external repositories as untrusted references until reviewed.
3. Never infer broker state, balance, authentication, order status, or execution from configuration alone.
4. Evidence must be current, attributable, reproducible, and reconciled.
5. Unknown, stale, contradictory, unauthenticated, or missing evidence is fail-closed.
6. Never print, commit, persist, or transmit secrets.
7. Never modify LIVE_LOCK, FINAL_EXECUTION_AUTHORIZATION, Risk Warden, Execution Firewall, Account Isolation, Balance Truth, or reconciliation semantics to make a task pass.
8. Research and tooling agents may recommend; only the existing AURELIA capital plane can authorize capital movement.
9. Every material change requires tests and an auditable rationale.
