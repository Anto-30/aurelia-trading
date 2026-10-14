# External Repository Capability Review

**Status:** Initial README, root-license-file, and AURELIA source-of-truth intake; not a full security audit, legal opinion, dependency approval, or integration test.
**Target system:** AURELIA, canonical repository `Anto-30/aurelia-trading`, branch `main`.
**Safety invariant:** Preserve `config/LIVE_LOCK.yaml`; external repositories have no capital or execution authority. No external code is vendored or imported by this review.

## Repository inventory

| Repository | Observed purpose from its README | Potential AURELIA use | Decision |
|---|---|---|---|
| [superset-sh/superset](https://github.com/superset-sh/superset) | Workspace for running CLI coding agents with terminals, code review, and browser previews; not Apache Superset BI | Optional developer workstation workflow | Evaluate separately; not a runtime dependency |
| [microsoft/TypeScript](https://github.com/microsoft/TypeScript) | Typed superset of JavaScript and compiler/tooling | Type-check any existing or future TypeScript operator UI | Use only where a TS application exists; not a trading engine dependency |
| [ClickHouse/clickhouse-connect](https://github.com/ClickHouse/clickhouse-connect) | Python driver for ClickHouse, Pandas/Arrow and related integrations | Research/event analytics storage and high-volume read-only reporting | Candidate optional analytics adapter after benchmark, schema, retention, security, and recovery review |
| [dataease/dataease](https://github.com/dataease/dataease) | Business-intelligence and visualization platform | Separate read-only operational/research dashboards | Optional standalone service only; modified GPLv3 terms need legal review |
| [lutinglt/superset-zh](https://github.com/lutinglt/superset-zh) | Chinese-localized Superset fork/image; README says it is no longer maintained and points users upstream | No required AURELIA use | Reject for new adoption; do not base deployment on unmaintained fork |
| [get-convex/convex-backend](https://github.com/get-convex/convex-backend) | Reactive database/backend with TypeScript server functions | Possible operator portal or notification state backend | Not a replacement for AURELIA ledger, broker truth, risk engine, or capital plane; FSL license needs careful review |
| [cvxpy/cvxpy](https://github.com/cvxpy/cvxpy) | Python modeling language for convex optimization | Offline portfolio constraints, allocation research, or constrained parameter studies | Research-only candidate; require reproducible benchmarks and independent mathematical validation |
| [get-convex/convex-js](https://github.com/get-convex/convex-js) | TypeScript/JavaScript SDK and client libraries for Convex | Client for an approved Convex-backed operator UI | Consider only if Convex is separately approved; not a standalone need |
| [cvxopt/cvxopt](https://github.com/cvxopt/cvxopt) | Python software for convex optimization | Alternative numerical solver for offline research | Do not add alongside CVXPY by default; GPL license and native/transitive dependencies need review |

## Root license-file observations

These are snapshots of the current default-branch root license files fetched during this review, not legal conclusions or complete dependency-license inventories.

- `superset-sh/superset`: `LICENSE.md` states Elastic License 2.0 (ELv2). Review its restrictions against intended internal/commercial use before adoption.
- `microsoft/TypeScript`: `LICENSE.txt` states Apache License 2.0.
- `ClickHouse/clickhouse-connect`: `LICENSE` states Apache License 2.0.
- `dataease/dataease`: `LICENSE` describes a modified GNU GPLv3 with additional conditions. Do not assume plain GPLv3; obtain legal review for intended deployment/distribution.
- `lutinglt/superset-zh`: root `LICENSE` states Apache License 2.0; repository README states the project is no longer maintained.
- `get-convex/convex-backend`: `LICENSE.md` states Functional Source License 1.1, Apache 2.0 Future License (FSL-1.1-Apache-2.0). Treat as source-available with specific terms, not simply Apache-2.0 today.
- `cvxpy/cvxpy`: root `LICENSE` states Apache License 2.0.
- `get-convex/convex-js`: root `LICENSE` states Apache License 2.0.
- `cvxopt/cvxopt`: root `LICENSE` describes a free-software license; the exact full terms and distribution obligations still require review before bundling or deployment.

## Preliminary architecture recommendations

1. Keep the canonical AURELIA implementation as the only trading engine and the only capital/execution authority.
2. Do not import external code into the execution path as part of this intake. External analytics must be read-only, least-privilege, and incapable of authorizing orders.
3. Prioritize a small, reversible proof of concept for ClickHouse Connect only if current data volume or query latency demonstrates a real need. First define data contracts, event-time semantics, idempotency, retention, encryption, access controls, backup/restore, and failure behavior.
4. Evaluate CVXPY before CVXOPT for an offline constrained-optimization experiment only if a specific optimization problem is documented. Solver output must never bypass strategy qualification, calibration, risk limits, or release gates.
5. Treat Superset (superset-sh) as an optional coding-agent workspace. Do not confuse it with Apache Superset or assume it is a production analytics service.
6. Do not deploy DataEase or Convex merely because their capabilities overlap with dashboards or state storage already available. Establish a concrete use case and threat model first.
7. Never place broker tokens, app IDs, credentials, or account data in external repositories, prompts, logs, dashboards, or analytics tables. Use protected secrets and sanitized evidence only.

## Required follow-up checks before adoption

- Record exact commit/tag and supported runtime versions for every candidate.
- Review full license text, notices, transitive dependency licenses, release activity, advisories, and security policy; root license files are not legal clearance.
- Run dependency and static security scans on a pinned revision in an isolated environment.
- Build a threat model and data-flow diagram, including outbound network access, authentication, secrets, telemetry, and privilege boundaries.
- For analytics, prove read-only access and test that service outage, stale data, or malformed output cannot authorize or submit an order.
- For optimization, define the objective, constraints, solver tolerances, infeasibility handling, numerical stability tests, benchmark set, and out-of-sample validation.
- Submit any implementation as a small isolated PR with tests and exact-commit evidence. Do not merge automatically.
- Preserve `config/LIVE_LOCK.yaml`: `live_trading_enabled: false`, `FINAL_EXECUTION_AUTHORIZATION: false`, and `LIVE_EXECUTION: BLOCKED` until all existing independent release gates are satisfied.

## Scope limitations

This is an initial README and root-license-file triage, not a complete source-code review. It does not establish vulnerability status, supported-version compatibility, dependency-chain license compatibility, build reproducibility, performance, or production readiness. No dependencies have been installed, no production services deployed, and no live trading enabled.
