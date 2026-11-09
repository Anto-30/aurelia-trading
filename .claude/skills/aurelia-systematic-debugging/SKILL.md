---
name: aurelia-systematic-debugging
description: Diagnose and remediate AURELIA runtime, CI, broker-adapter, state-machine, and deployment failures using evidence-first root-cause analysis. Use for AURELIA defects and runtime incidents.
---

# AURELIA Systematic Debugging

1. Read `CLAUDE.md`, `AGENTS.md`, `config/LIVE_LOCK.yaml`, and the relevant architecture and assurance contracts.
2. Capture the exact failure: workflow ID/job, commit SHA, exception, failing assertion, source path, and input provenance. Separate observation from hypothesis.
3. Trace caller → adapter/transport → state machine → journal/ledger/idempotency → risk/firewall → evidence writer → validator → workflow/release gate.
4. Find the earliest incorrect state transition or contract mismatch. Do not patch the final symptom before locating its producer.
5. Build an offline reproducer using deterministic fake transports and bounded fixtures. Do not connect to a live broker, production host, secret store, or authenticated browser profile.
6. Make the smallest responsible fix. Add one positive regression and negative tests for missing, mismatched, stale, duplicate, malformed, and unauthorized inputs as applicable.
7. Verify all failure paths remain fail-closed and `config/LIVE_LOCK.yaml` is unchanged.
8. Run targeted tests and the relevant suite. Cite actual CI run IDs and exact head SHA; do not infer success from a commit or queued workflow.
9. Preserve failure reports and artifacts. Never create fake operational evidence or relabel an unsuccessful run.
10. Report cause, changed files, exact verification, residual risk, blockers, and next safe action.

## Special cases

- `STATE UNKNOWN` is a block, not a default or retry signal.
- Broker timeouts/unknown outcomes must not trigger blind order resubmission.
- Evidence schema changes must be matched to true producers, not just test fixtures.
- A 3,600-second soak is a real timed observation, not a static test or simulated elapsed duration.
- A sealed OOS campaign is immutable; any strategy/config change starts a new campaign.
