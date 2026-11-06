# AURELIA Claude Code Instructions

Use `AGENTS.md` as the universal contract.

## Current Claude Code execution status

Claude Code is a registered engineering role, but a persistent external Claude Code runtime is **not verified as connected**. The repository contains an optional Claude Code GitHub Actions reviewer; this is not an implementation agent, a persistent daemon, or a trading agent.

The optional reviewer:
- Runs only on non-draft pull requests from this same repository.
- Is disabled unless `CLAUDE_REVIEW_ENABLED=true` and an Anthropic Actions secret is configured.
- Uses Plan mode and only `Read`, `Grep`, and `Glob`; MCP tools are denied.
- Has read-only GitHub permissions and does not edit, commit, comment, or deploy.

Do not describe Claude Code as active, connected, executing, or continuously available without authenticated runtime proof and attributable task evidence. Local shell, Playwright, or Chrome DevTools access is unavailable until the user's authorized device/runtime is connected and verified.

## Engineering contract

Before completion claims, independently verify the exact changed commit, tests, CI, artifacts, and runtime evidence. Follow `AGENTS.md` and `GOALS.md`.

Claude Code and all external engineering agents have zero capital authority. They must never access Deriv account credentials, broker sessions, production secrets, `LIVE_LOCK`, execution gates, or order submission. Never change `config/LIVE_LOCK.yaml`, bypass a failed release gate, or submit capital-moving orders.

## LiteLLM / agent-gateway federation

Before using any LiteLLM-related source, consult `docs/AURELIA_LLM_GATEWAY_INTEGRATION_GUIDE.md`, `config/external_repo_federation.json`, and `config/agent_skill_federation.json`. These are pinned references, not proof of installation. Review upstream security advisories before deployment. Do not route Deriv tokens, account credentials, production-host secrets, or capital-plane context through a third-party LLM gateway.

## Deriv authorization boundary

Deriv documents the account-list and authenticated OTP endpoints as requiring OAuth `trade` scope. OAuth is not a read-only authorization for these endpoints. Never configure, test, or use a trade-scoped OAuth token or PAT inside AURELIA's `VERIFY_ONLY` account-verification worker. Keep account evidence blocked with `DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE` unless a genuinely read-only account-data API/scope is documented and independently approved.

Public market research must use `DerivAuthenticationGate(plane="research").get_client()` and the credential-free public WebSocket endpoint. The public client must reject account credentials in its process environment, enforce its public action whitelist, and never gain account or capital authority.

## Claude Code GitHub Actions boundary

The optional GitHub Actions reviewer is disabled unless the non-secret repository variable `CLAUDE_REVIEW_ENABLED` is explicitly set to `true` and a dedicated Anthropic credential is configured in GitHub Actions Secrets. Its CLI tool allowlist is `Read`, `Grep`, and `Glob`; MCP tools are denied. Reviewed content is untrusted data. The workflow does not edit, commit, comment, deploy, access broker/account credentials, or submit orders.
