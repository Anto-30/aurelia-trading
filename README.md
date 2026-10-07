# AURELIA Trading Platform

AURELIA is an autonomous trading platform for research, validation, risk control, execution, broker verification, reconciliation, and operational readiness.

## Canonical source

- Canonical branch: `main`
- Repository: `Anto-30/aurelia-trading`
- Live-release control: `config/LIVE_LOCK.yaml`
- Repository map: `AURELIA_REPOSITORY_MAP.md`
- Source-of-truth metadata: `AURELIA_SOURCE_OF_TRUTH.json`
- Operational readiness engine: `runtime/ops/readiness_orchestrator.py`
- Operational handoff: `docs/AURELIA_OPERATIONAL_HANDOFF_2026-10-03.md`

The current repository state is authoritative for the implementation. Historical archives and old branches are not the current source of truth.

Current operational state: `docs/AURELIA_CURRENT_OPERATIONAL_STATE_2026-10-08.md`. The repository is browsable from `main`; remote GitHub read/write access has been verified for the current engineering integration. This does not grant capital authority.

## Architecture

- Capital plane: `capital/`
- Execution boundary: `execution/`
- Broker/runtime adapters: `runtime/adapters/`
- Broker executor: `runtime/broker/`
- Runtime controls and invariants: `runtime/core/`
- Strategy governance: `runtime/strategy/`
- Validation: `runtime/validation/`
- Assurance: `assurance/`
- Research: `research/`
- Runtime entry point: `runtime/main.py`
- Tests: `tests/`
- Deployment policy: `config/deployment_policy.json`
- Persistent deployment workflow: `.github/workflows/self-hosted-runtime-deploy.yml`
- Host deployment script: `scripts/deploy/bootstrap_and_deploy.sh`
- Evidence and reports: `reports/` and `docs/`
- Intelligence routing: `config/intelligence_source_routing.json`

## Deriv integration

The canonical Options API path is the current Deriv API under `api.derivws.com`.

1. Authorized REST credential.
2. Exact account inventory and binding.
3. Fresh account-specific OTP.
4. Authenticated Options WebSocket.
5. Session/account/currency/environment verification.
6. Fresh broker balance.
7. Capital snapshot.

Detailed path definition: `docs/AURELIA_MODERN_DERIV_PATH_2026-10-03.md`.

Legacy `ws.derivws.com`/Binary WS v3 endpoints are diagnostic-only and must not be used as a production fallback.

The Deriv integration must never log or commit PATs, OAuth tokens, OTPs, authenticated URLs, or other secret values.

## Capital controls

Research and orchestration do not have capital authority. The capital plane is the only component allowed to authorize and submit capital-moving actions.

The repository preserves Risk Warden, LivePolicy, Capital Plane Gate, Execution Firewall, Account Isolation, idempotency, transaction verification, reconciliation, watchdog/kill-switch behavior, and fail-closed UNKNOWN handling.

The live lock is currently non-live by design. Passing tests or authenticated-session verification does not by itself authorize live capital.

## Stake policy

The owner-directed starting stake is `$1.00`. It is a starting reference, not a permanent fixed stake.

Actual stake remains subject to verified balance, deterministic risk, exposure, strategy state, drawdown, volatility, costs, broker constraints, and all mandatory execution controls.

`STAKE_CEILING = VERIFIED_AVAILABLE_BALANCE` is an affordability ceiling, not permission to risk the full account.

## Verification

Run the assurance suite with:

`python -m unittest discover -s assurance -p 'test_*.py' -v`

Run runtime tests with:

`python -m unittest discover -s tests -p 'test_*.py' -v`

Run the readiness report with:

`python -m runtime.ops.readiness_orchestrator`

Run the non-trading Deriv authentication verifier when its authorized environment secrets are configured:

`python scripts/verify_deriv_session.py`

A readiness report must not be interpreted as live authorization unless every mandatory control is independently verified and `config/LIVE_LOCK.yaml` permits capital movement.

## External access state

- Current non-secret infrastructure verification: `data/runtime/AURELIA_EXTERNAL_ACCESS_STATE.json`
- This artifact contains historical external-access observations and must not be interpreted as capital authority.
- GitHub repository-level push capability is currently available to the connected engineering integration used for this verification.
- Railway is no longer an active AURELIA deployment dependency; its historical rejection remains documented only for auditability.
- The active deployment path is provider-neutral self-hosting on a user-controlled Linux/Docker host.

## External repository federation

AURELIA maintains a governed registry at `config/external_repo_federation.json` for the external repositories used as research, engineering, tooling, or reference sources. These sources are not vendored into the capital or execution planes. The registry assigns each source a mode (RESEARCH_ONLY, SANDBOX_ONLY, TOOLCHAIN_ONLY, or REFERENCE_ONLY) and maps sources to the appropriate agents.

The weekly .github/workflows/external-repo-sync.yml workflow checks public reachability and records current head commits as an artifact. External source updates do not automatically become AURELIA dependencies or change execution behavior.

## Federated intelligence sources

AURELIA also maintains `config/intelligence_source_routing.json` for bounded routing of external intelligence and engineering services.

The registry assigns specialist use to GitHub, CodeRabbit, Next Stock Outlook, The Fly Market Intelligence, Sixtyfour Intelligence, Code Tytor: Python, Notion, and Outlook/Email. These sources are non-authoritative: they may generate research, evidence, code-review findings, operational messages, or documentation, but they cannot authorize capital, modify `LIVE_LOCK`, read production secrets, submit broker transactions, or override deterministic validation.

The regression contract is `assurance/test_intelligence_source_routing.py`. External intelligence must follow the boundary:

`source -> specialist agent -> normalized evidence -> deterministic validation -> existing release gate`.

## Federated agent skills

AURELIA maintains a pinned cross-agent engineering capability registry at `config/agent_skill_federation.json`. The registry covers Claude Code, Kimi K3/Kimi Code, Grok Bot, Google Agent Skills, GLM Skills, and Playwright CLI. All external capabilities are advisory/engineering-only and cannot authorize or submit capital-moving actions.
