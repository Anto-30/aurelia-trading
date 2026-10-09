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
