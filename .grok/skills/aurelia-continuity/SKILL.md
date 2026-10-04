---
name: aurelia-continuity
description: Keep AURELIA research and engineering agents continuously ready through deterministic startup checks, heartbeat monitoring, recovery diagnostics, and fail-closed safety assertions.
---

At every session start:
1. Resolve the canonical repository tip on main.
2. Read the live lock and capability boundary.
3. Load evidence reconciliation state.
4. Detect stale CI/evidence metadata.
5. Verify external skill/plugin pins before using them.
6. Start role-specific work only after the safe core passes.

Continuity rules:
- Agents may remain continuously available for research, diagnosis, testing, documentation, and repair.
- External agents never receive capital authority.
- A dropped session is a recoverable infrastructure event, not permission to bypass controls.
- Unknown, stale, drifted, or unavailable authorization state is fail-closed.
- Use the AURELIA heartbeat to re-enter the safe startup path after restart.