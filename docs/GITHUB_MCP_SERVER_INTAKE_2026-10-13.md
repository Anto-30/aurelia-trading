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

## Assurance evidence inspected — 2026-10-13

PR #123: https://github.com/Anto-30/aurelia-trading/pull/123

At PR head `e6cceb270909cd952d3866e9ff61135e36d164ee`, these PR-associated workflows completed successfully:
- AURELIA Assurance #2794: https://github.com/Anto-30/aurelia-trading/actions/runs/38443202548
- Agent Federation Audit #1072: https://github.com/Anto-30/aurelia-trading/actions/runs/38443201915
- Agent Continuity Watchdog #1107: https://github.com/Anto-30/aurelia-trading/actions/runs/38443202380

**Commit-provenance qualification:** The Assurance PR event checked the synthetic GitHub merge ref at `f8fece41b0172031fdc34bb80484250ea93eb27f`, as confirmed in the workflow checkout log and the public-transport evidence artifact. These runs therefore establish successful CI on the PR merge result, not an exact branch-head checkout of `e6cceb270909cd952d3866e9ff61135e36d164ee`. A non-main branch-push assurance run is required to close the exact-source check; verify its recorded `head_sha` against that run's actual source commit before final review.

### What passed
- Python compilation, production static acceptance audit, optimized-mode governance validators, research-plane tests, assurance tests, runtime tests, secret-presence tests, hardening tests, runtime container build, public Deriv market-data transport probe, and local health smoke test completed successfully.
- Static acceptance output reported probability policy `0.55..0.75`, `CAPITAL_MOVEMENT_PERMITTED=false`, `FINAL_EXECUTION_AUTHORIZATION=false`, and `LIVE_EXECUTION=BLOCKED`.
- Both `pip-audit -r requirements.txt` and `pip-audit .` reported no known vulnerabilities.
- Bandit artifact: https://github.com/Anto-30/aurelia-trading/actions/runs/38443202548/artifacts/11837201281. The report records 0 HIGH, 0 MEDIUM, and 22 LOW findings. The 22 LOW findings remain recorded for review; a passing scanner job is not an independent security audit.

### Still blocked — explicitly not certified
- Deriv authentication prerequisites artifact: https://github.com/Anto-30/aurelia-trading/actions/runs/38443202548/artifacts/11836846658. Safe prerequisite metadata says authentication is not configured; token, expected account ID, and expected currency are absent. The authenticated real-account session, read-only account evidence, and verify-only transaction lifecycle steps were skipped.
- Readiness and certification reported `NOT_READY` because nine production artifacts were absent: `evidence/strategy_eligibility.json`, `evidence/prospective_oos.json`, `evidence/calibration.json`, `evidence/execution_economics.json`, `evidence/soak_3600s.json`, `evidence/broker_lifecycle.json`, `evidence/recovery_matrix.json`, `evidence/security_audit.json`, and `evidence/deployment.json`.
- Source-bound, fresh, account/currency/contract-bound broker minimum-stake evidence is not implemented by the adapter. Caller-supplied numbers are not broker proof; LIVE authorization must continue to fail closed until this contract is implemented and adversarially tested.
- `config/LIVE_LOCK.yaml` remains locked: `live_trading_enabled: false`, `FINAL_EXECUTION_AUTHORIZATION: false`, `LIVE_EXECUTION: BLOCKED`, `capital_plane_mode: VERIFY_ONLY`.
- No authenticated real-account lifecycle, prospective OOS qualification, calibration/cost qualification, 3,600-second soak, independent security audit, or production deployment/runtime verification is claimed.

## Release disposition
PR #123 remains open and draft. Keep LIVE locked. Do not treat CI success as broker evidence or production readiness. After exact-source assurance is verified, request independent code/security review for the code change; release qualification remains separately blocked until every required external artifact is valid, fresh, and bound to the correct source and account. No live order or production release is authorized by this intake.
