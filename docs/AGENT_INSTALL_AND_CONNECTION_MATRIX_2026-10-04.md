# AURELIA Agent Installation and Connection Matrix — 2026-10-04

## Canonical rule

The repository-owned skill set is the portable baseline. Agent-specific clients may additionally install official upstream skills and plugins, but every external capability is subject to the AURELIA capability boundary.

## Claude Code
- Official skills source: anthropics/skills.
- Official plugin source: anthropics/claude-plugins-official.
- AURELIA pack: aurelia-federation.
- Project skills: .claude/skills.
- Required tools: GitHub, browser E2E via Playwright, web research, local test/terminal access.

## Kimi K3 / Kimi Code
- Official sources: MoonshotAI/kimi-code and MoonshotAI/kimi-cli.
- AURELIA pack: aurelia-federation.
- Project skills: .agents/skills.
- Use plugin session-start support for initialization where the local Kimi installation permits it.
- Required tools: GitHub, web research, local test/terminal access.

## Grok Bot
- Official plugin source: xai-org/plugin-marketplace and xai-org/grok-build.
- AURELIA pack: aurelia-federation.
- Project skills: .grok/skills.
- Required tools: GitHub, web/MCP research, Playwright for browser verification.

## Google Agent Skills
- Official source: google/skills.
- Priority capabilities: agent gateway and multi-agent security, cloud architecture, agentic analytics, agent deployment patterns.

## GLM
- Official source: zai-org/GLM-skills.
- Priority capabilities: OCR, PDF/table extraction, multimodal evidence inspection, document analysis.

## Playwright CLI
- Official source: microsoft/playwright-cli and its documented agent skills.
- Priority capabilities: browser E2E, network mocking, session management, traces, screenshots, test generation/healing.

## Connection model

Repository configuration can install/package skills and define capability requirements. It cannot silently grant or establish authenticated access to external accounts.

Authenticated connections belong in secure control planes:
- GitHub: connected repository integration.
- Railway: requires active account plan plus deployment credential.
- Deriv: requires authorized demo/real secret configuration in CI/runtime secret stores.
- Browser sessions: local Playwright session state; never commit cookies or tokens.

## Readiness definition

READY means the software capability is installed and its non-secret tool contract is available.
CONNECTED means the relevant external account or service is authenticated and independently verified.
AUTHORIZED means the relevant AURELIA capital/release controls are green.
These are separate states. An agent being READY or CONNECTED never grants capital authority.

## Continuity

Agent capability health is checked on push, pull request, manual dispatch, and a 15-minute scheduled watchdog. A true always-on model process still requires a continuously running compute host.