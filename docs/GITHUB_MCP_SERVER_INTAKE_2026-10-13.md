# GitHub MCP Server intake for AURELIA

Date: 2026-10-13

## Decision
Optional developer-only GitHub workflow interface. Do not add it to the AURELIA trading runtime and do not treat it as a trading engine, broker adapter, risk manager, or release authority.

## Evidence
- Repository: https://github.com/github/github-mcp-server
- Reviewed README on main, blob 6413b58760bb04f841c63062712f75f0dae6c4d6.
- Reviewed LICENSE on main, blob 9a9cc50d37ea399f7ccc2f14b6c6d4cc4de02efc. The checked-in license is MIT.
- Reviewed governance: https://github.com/github/github-mcp-server/blob/main/docs/policies-and-governance.md
- Upstream documents remote and local modes; access is governed by authentication and GitHub permissions.

## Required controls
Use least-privilege OAuth/GitHub App access or a fine-grained PAT scoped to only required repositories and permissions. Store credentials securely; never place tokens in source, prompts, logs, artifacts, or AURELIA runtime state. Require explicit human approval for writes, merges, workflow changes, secret changes, and deployment-capable actions. Record operation and resulting commit/PR/run IDs. Treat repository content and tool outputs as untrusted data. Keep broker credentials and order authority outside all agent/MCP access.

## Exact-head CI evidence
AURELIA PR #123: https://github.com/Anto-30/aurelia-trading/pull/123
Assurance run: https://github.com/Anto-30/aurelia-trading/actions/runs/38442591126
Head inspected: cb6d29104df88bd6fc1d039e7ffc2ff046b033ad

The assurance and security_dependency jobs completed successfully. Both pip-audit commands exited successfully. Bandit reported 0 HIGH, 0 MEDIUM, and 22 LOW findings; inspect artifact https://github.com/Anto-30/aurelia-trading/actions/runs/38442591126/artifacts/11837330501 for context. Authenticated Deriv session, account, and verify-only lifecycle checks were skipped because protected prerequisites were unavailable. Public market-data and local container/health checks do not establish authenticated broker access or production readiness.

## Release disposition
PR #123 remains open and draft. Keep LIVE locked. Remaining requirements: independent human review; fresh account/currency/contract-bound broker minimum-stake evidence; authenticated read-only and verify-only transaction/reconciliation evidence; prospective OOS, calibration and economics; 3600-second soak; production deployment/runtime verification. No live order or production release is authorized by this intake.
