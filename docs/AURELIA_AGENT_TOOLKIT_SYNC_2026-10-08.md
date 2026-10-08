# AURELIA Agent Toolkit Sync — 2026-10-08

This registry maps the requested repositories into the AURELIA engineering/research federation.

## Agent routing

- ClaudeCode: implementation, dependency analysis, security review, prompt/tooling adaptation.
- GrokBot: orchestration, architecture review, research synthesis, workflow design.
- JEV: validation, evidence audit, regression testing, workflow verification.
- AURELIA: registry enforcement, routing, deterministic integration gates and production safety.

## Recommended use

1. github/spec-kit is the primary spec/bug/convergence workflow reference.
2. microsoft/PromptKit is the prompt-engineering and prompt-drift reference.
3. CopilotKit/CopilotKit is the UI/human-in-the-loop reference for Command Center work.
4. All-The-Vibes/ATV-StarterKit and ikcode-dev/copilot-kit are engineering-workflow references.
5. github/spec-kit-copilot is the Copilot-specific adapter for Spec Kit.
6. microsoft/Power-CAT-Copilot-Studio-Kit is a testing/governance/observability reference only.
7. microsoft/Employee-Self-Service-Agent-Developer-Kit is a validation/agent-development reference only.
8. TheMattBerman/google-ads-copilot is a generic staged-action/auditability reference only; its Google Ads functionality is not imported into trading.

## Safety boundary

These repositories cannot authorize a trade, mutate config/LIVE_LOCK.yaml, read production secrets, bypass Risk Warden or Execution Firewall, alter broker credentials, or promote an external implementation directly into the capital plane.

Any useful implementation must be re-created or adapted inside AURELIA, reviewed, tested, and evidenced before promotion.

## Pinned sources

See config/external_repo_federation_copilot_agent_addendum.json for exact repository heads and promotion policy.
