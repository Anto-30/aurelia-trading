# OpenWiki and AI-Infra-Guard Adoption Plan

Status: proposed, documentation-only; tools are not installed or executed by this change.
Canonical repository: `Anto-30/aurelia-trading`
Canonical branch: `main`
Change branch: `docs/openwiki-ai-infra-guard-adoption`

## Decision

Evaluate both tools as development-time aids only. Do not vendor either upstream codebase into AURELIA's capital plane, execution plane, or production runtime. Do not allow either tool to authorize orders, mutate `config/LIVE_LOCK.yaml`, read production secrets, change deployment policy, or bypass deterministic release gates.

## OpenWiki: repository documentation

Upstream: https://github.com/langchain-ai/openwiki
License reported by upstream repository: MIT.
Upstream quick start currently documents Node.js >=22.22.0 and `npm install -g openwiki`; verify the current upstream README and release before use.

Proposed isolated workflow:
1. Run only in a disposable development checkout or a short-lived branch/worktree.
2. Review `openwiki/INSTRUCTIONS.md` before generation and ensure it prohibits secret discovery, copying credentials, and treating generated claims as authorization.
3. Generate a draft wiki, then review every architecture, API, operational, and security claim against source files and tests.
4. Keep generated output in a dedicated documentation path; do not overwrite canonical operational documents or `AGENTS.md`/agent instructions without review.
5. Submit documentation changes as a pull request. Do not auto-merge generated content.
6. Re-run generation on a disposable copy first when evaluating updates, because initialization may replace generated wiki content.

Acceptance criteria:
- Every material claim links to a real source file or test.
- No secret values, environment dumps, or production-only details are emitted.
- No live-lock, risk-policy, release-authority, or execution code is changed.
- Generated pages are reviewed for accuracy and staleness before merge.

## AI-Infra-Guard: security assessment

Upstream: https://github.com/Tencent/AI-Infra-Guard
License reported by upstream repository: Apache-2.0.
Upstream documentation warns that the full-stack service currently lacks authentication and must not be exposed on public networks. The upstream skill scanner documents `LLM_API_KEY` and an external model/API route for scans.

Proposed isolated workflow:
1. Prefer static review and the smallest relevant scanner component first; do not deploy the full web platform unless the security owner has approved an isolated local environment.
2. If the full platform is evaluated, bind it to loopback/private isolated networking only, use disposable data, and verify authentication/network exposure before starting it.
3. Run scanner tests against intentionally benign fixture skills/MCP descriptions, never against production agents or live broker connections.
4. Treat scanner output as advisory findings. Triage false positives and reproduce high-severity findings independently.
5. Do not pass Deriv credentials, PATs, OAuth tokens, OTPs, production environment files, or private runtime logs to an external LLM/API provider. If an external model key is required, keep it in a local ephemeral environment and never place it in source, artifacts, or chat.
6. Convert confirmed findings into reviewed fixes and regression tests; do not let scanner output automatically modify production configuration or execute remediation.

Acceptance criteria:
- No service is exposed publicly without authentication and an explicit security review.
- No production secrets or broker-connected sessions are supplied to scanners.
- Findings include evidence, severity, reproduction steps, disposition, and regression coverage where applicable.
- Critical unresolved findings block promotion of the affected integration, not unrelated trading components.

## AURELIA non-negotiable controls

The checked-in `config/LIVE_LOCK.yaml` remains authoritative. Its current state is non-live:
- `live_trading_enabled: false`
- `FINAL_EXECUTION_AUTHORIZATION: false`
- `LIVE_EXECUTION: BLOCKED`
- `capital_plane_mode: VERIFY_ONLY`
- `research_capital_authority: false`

Neither tool may change these fields or receive authority to submit broker transactions. Documentation generation, a clean scanner result, passing CI, and successful authentication checks do not constitute live-release authorization. Existing strategy qualification, calibration, cost validation, persistent runtime, reconciliation, soak, and independent release gates remain mandatory.

## Verification and rollout sequence

1. Review this plan and upstream license, security notes, release state, and installation instructions.
2. Perform isolated tool evaluation in a disposable development environment; do not install into the trading runtime.
3. Record exact tool versions/commit pins, commands, environment requirements, logs with secrets excluded, and test outcomes.
4. Review generated documentation and security findings independently.
5. Add only reviewed documentation or scanner checks to CI; CI must fail closed on policy violations and must not receive production secrets.
6. Open a separate implementation PR only after the isolated evaluation passes.
7. Merge only after required checks and independent human review.

## Current evidence boundary

This file records an adoption plan, not proof of installation, scan completion, generated documentation quality, CI integration, or production readiness. Those states must be updated only with reproducible evidence from the actual isolated run.
