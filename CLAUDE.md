# AURELIA Claude Code Instructions

Use `AGENTS.md` as the universal contract.

Claude Code is the primary implementation/review agent. Prefer:
- GitHub for repository, PR, CI, and issue work.
- Playwright for browser/E2E verification.
- security-review for supply-chain and privilege analysis.
- ci-diagnostics for workflow failures.
- evidence-inspection for reports/screenshots/PDFs.
- aurelia-federated-repair for cross-agent coordination.

Before completion claims, independently verify the exact changed commit and required CI evidence.

Claude Code has zero capital authority.

## Continuous operations goal

Use `GOALS.md` as the goal and acceptance contract for the ChatGPT + Claude Code supervisory model. Work through its immediate execution order and report evidence for each acceptance state. Prioritize continuously progressing research and a verified persistent runtime; do not claim that scheduled jobs equal an always-on daemon. Keep Claude Code at zero capital authority. Never flip `config/LIVE_LOCK.yaml`, bypass a failed release gate, or submit capital-moving orders. Escalate missing account authentication or protected secrets for configuration through the secure provider UI, without printing or committing them. Live authorization must remain blocked until the existing deterministic policy and independent release authority approve it.


## LiteLLM / agent-gateway federation

Before using any LiteLLM-related source, consult `docs/AURELIA_LLM_GATEWAY_INTEGRATION_GUIDE.md`, `config/external_repo_federation.json`, and `config/agent_skill_federation.json`. These sources are pinned references, not proof of installation. Review the upstream security advisories before any deployment. Do not route Deriv tokens, account credentials, production-host secrets, or any capital-plane context through a third-party LLM gateway. Do not change `config/LIVE_LOCK.yaml` or execution gates.


## AURELIA evidence and system-debugging guardrails

For system remediation, use the repository-local skills:
- `.claude/skills/aurelia-systematic-debugging/SKILL.md`
- `.claude/skills/aurelia-evidence-engineering/SKILL.md`

Treat `docs/engineering/EXTERNAL_TOOL_ADOPTION.md` and `config/external_tool_intake_2026-11-09.json` as the reviewed intake record for the additional repositories supplied on 2026-11-09. The intake does not install or authorize every source. Follow each entry's adoption status and assigned roles.

All external executables and agents remain denied by default. Qwen Code and Open Interpreter are sandbox/developer references only; do not run them on a production host or against a signed-in broker/browser session. Keep paste-site OSINT collectors out of the project. Use Ruff only through the pinned development extra, never in the production image.

Do not claim DeepSeek, Hermes, Qwen Code, Open Interpreter, or another agent has been installed, connected, or run unless the device/runtime identity and its attributable execution record are verified. The canonical agent matrix is in `config/agent_tool_skill_assignment.json`; this change adds repository-local task guidance, not external accounts or persistent workers.


## 2026-11-11 external repository intake

Before using repositories supplied on 2026-11-11, read docs/engineering/EXTERNAL_TOOL_ADOPTION_2026-11-11.md, config/external_tool_intake_2026-11-11.json and config/external_repository_agent_assignments_2026-11-11.json. Use the existing AURELIA debugging/evidence skills. No upstream package, agent, hook, plugin or executable is installed by this intake. Follow each disposition and installation gate. No secrets, broker access, order/capital authority, LIVE_LOCK mutation or production deployment.
