# AURELIA Trading Platform

AURELIA is an autonomous trading platform for research, validation, risk control, execution, broker verification, reconciliation, and operational readiness.

## Canonical source

- Canonical branch: `main`
- Repository: `Anto-30/aurelia-trading`
- Live-release control: `config/LIVE_LOCK.yaml`
- Repository map: `AURELIA_REPOSITORY_MAP.md`
- Source-of-truth metadata: `AURELIA_SOURCE_OF_TRUTH.json`
- GitHub source-of-truth audit: `docs/AURELIA_GITHUB_SOURCE_OF_TRUTH_2026-10-03.md`
- Operational readiness engine: `runtime/ops/readiness_orchestrator.py`
- Operational handoff: `docs/AURELIA_OPERATIONAL_HANDOFF_2026-10-03.md`

The current repository state is authoritative for the implementation. Historical archives and old branches are not the current source of truth.

Current operational state: `docs/AURELIA_CURRENT_OPERATIONAL_STATE_2026-10-03.md`. The repository is browsable from `main`; remote GitHub repository-level read/write capability is verified by the connected engineering integration. This does not grant capital authority.

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
- Deployment: `railway.toml` and `.github/workflows/railway-deploy.yml`
- Evidence and reports: `reports/` and `docs/`

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

Run the repository source-of-truth regression:

`python -m unittest tests.test_repository_source_of_truth -v`

A readiness report must not be interpreted as live authorization unless every mandatory control is independently verified and `config/LIVE_LOCK.yaml` permits capital movement.

## External access state

- Current non-secret infrastructure verification: `data/runtime/AURELIA_EXTERNAL_ACCESS_STATE.json`
- This artifact distinguishes repository-level GitHub access, Railway deployment state, and operator-reported broker runtime evidence.
- GitHub repository-level push capability is available to the connected engineering integration used for this verification.
- Railway currently has no service/deployment in the existing project; deployment creation is blocked by the Railway account's expired trial/plan requirement.
