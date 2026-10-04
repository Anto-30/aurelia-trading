# AURELIA Agent Continuity and Capability Architecture — 2026-10-04

## Objective

All engineering and research agents should start with the same safe core, discover role-specific skills, and continuously re-enter the same fail-closed checks after restart.

## Agent assignments
- Claude Code: primary implementation, testing, PR repair, CI diagnostics, browser E2E.
- Kimi K3/Kimi Code: parallel analysis, adversarial reviews, test strategy and cross-checks.
- Grok Bot: orchestration, research intelligence, blocker diagnosis, ecosystem and skill registry synchronization.
- Google Agent Skills: multi-agent security, agent gateway patterns, cloud and deployment architecture.
- GLM Skills: OCR, PDF/document/table/image evidence inspection.
- Playwright CLI: browser/UI/session/network/tracing/E2E verification.
- AURELIA: sole capital and execution authority.

## Canonical skill distribution

The repository skills directory is canonical.

Run: python scripts/agent_capability_sync.py

This synchronizes safe core skills into .claude/skills, .grok/skills, and .agents/skills.

## External ecosystem policy

Official upstream sources are pinned in config/agent_skill_federation.json. They contribute implementation patterns and selected skills, not capital authority. Community catalogs are discovery-only.

## Continuity

GitHub Actions runs a watchdog on every push/PR and every 15 minutes. This provides recurring verification and re-entry into the safe startup path. It does not claim that a stateless model session is literally immortal.

A true always-on agent process requires a continuously running compute worker. The current Railway worker remains unavailable until its external account-plan blocker is resolved.

## Capital safety

No continuity feature may flip the live lock, grant external-agent capital authority, submit orders, read or log secrets, treat UI or simulation evidence as broker truth, or bypass Risk Warden, Capital Plane, Execution Firewall, Account Isolation, idempotency, reconciliation, watchdog, or kill-switch controls.