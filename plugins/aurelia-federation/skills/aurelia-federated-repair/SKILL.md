---
name: aurelia-federated-repair
description: Use when AURELIA needs cross-agent diagnosis, certification repair, CI/evidence reconciliation, browser verification, security review, or integration of external agent skills/plugins.
version: 1.0.0
---

Use the canonical repository `main`, preserve the existing AURELIA architecture, and treat all external agents as engineering/research-only.

Federate tasks:
- Claude Code: implementation, tests, code review, plugin/skill structure.
- Kimi K3/Kimi Code: parallel analysis and adversarial cross-checks.
- Grok Bot: orchestration, ecosystem discovery, blocker diagnosis.
- Google Agent Skills: multi-agent security and deployment architecture review.
- GLM: multimodal/PDF/image/table evidence inspection.
- Playwright CLI: browser/session/network/E2E verification.

Repair loop:
inspect -> reproduce -> isolate -> smallest fix -> deterministic tests -> evidence capture -> state reconciliation -> certification re-check.

Hard rules:
- FINAL_EXECUTION_AUTHORIZATION=false.
- LIVE_EXECUTION=BLOCKED.
- No external agent has capital authority.
- Never read, print, or commit secrets.
- Never create or use a second trading engine.
- Never promote simulation evidence to broker/transaction/production evidence.
- Fail closed on UNKNOWN, stale, invalid, drifted, or uncalibrated authorization inputs.
