---
name: security-review
description: Perform security, supply-chain, secret-hygiene, privilege-boundary, and agent-tooling reviews of AURELIA.
---

Check unpinned external dependencies, executable plugin hooks, MCP/LSP trust boundaries, secret exposure in logs/artifacts, privilege escalation paths, live-lock mutation paths, agent-to-capital authority crossings, unsafe browser automation, and CI permissions.
Fail closed when a control cannot be verified.