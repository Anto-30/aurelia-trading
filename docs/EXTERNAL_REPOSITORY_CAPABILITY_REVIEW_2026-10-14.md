# External Repository Capability Review

**Status:** Initial README-level intake; not a security audit, license clearance, dependency approval, or integration test.
**Target system:** AURELIA, canonical repository `Anto-30/aurelia-trading`, branch `main`.
**Safety invariant:** Preserve `config/LIVE_LOCK.yaml`; external repositories have no capital or execution authority. No external code is vendored or imported by this review.

## Repository inventory

| Repository | Observed purpose from its README | Potential AURELIA use | Decision |
|---|---|---|---|
| [superset-sh/superset](https://github.com/superset-sh/superset) | Workspace for running CLI coding agents with terminals, code review, and browser previews; this is not Apache Superset BI | Optional developer workstation workflow | Evaluate separately; do not add as a runtime dependency |
| [microsoft/TypeScript](https://github.com/microsoft/TypeScript) | Typed superset of JavaScript and compiler/tooling | Type-check any existing or future TypeScript operator UI | Use the installed ecosystem/toolchain only where a TS application exists; not a trading engine dependency |
| [ClickHouse/clickhouse-connect](https://github.com/ClickHouse/clickhouse-connect) | Python driver for ClickHouse, Pandas/Arrow and related integrations | Research/event analytics storage and high-volume read-only reporting | Candidate for an optional analytics adapter after benchmark, schema, retention, security, and recovery review |
| [dataease/dataease](https://github.com/dataease/dataease) | Open-source business-intelligence and visualization platform; README advertises GPL-3.0 | Separate read-only operational/research dashboards | Optional standalone service only; review GPL obligations and deployment isolation before adoption |
| [lutinglt/superset-zh](https://github.com/lutinglt/superset-zh) | Chinese-localized Superset fork/image; README says it is no longer maintained and points users to upstream | None required for AURELIA | Reject as a new dependency; do not base a deployment on an unmaintained fork |
| [get-convex/convex-backend](https://github.com/get-convex/convex-backend) | Reactive database/backend with TypeScript server functions | Possible operator portal or notification state backend | Not a replacement for AURELIA's ledger, broker truth, risk engine, or capital plane; defer pending architecture/security review |
| [cvxpy/cvxpy](https://github.com/cvxpy/cvxpy) | Python modeling language for convex optimization | Offline portfolio constraints, allocation research, or constrained parameter studies | Research-only candidate; require reproducible benchmarks and independent mathematical validation |
| [get-convex/convex-js](https://github.com/get-convex/convex-js) | TypeScript/JavaScript SDK and client libraries for Convex | Client for an approved Convex-backed operator UI | Consider only if Convex is separately approved; paired with backend, not a standalone need |
| [cvxopt/cvxopt](https://github.com/cvxopt/cvxopt) | Python software for convex optimization; README advertises GPL-3.0 | Alternative numerical solver for offline research | Do not add alongside CVXPY by default; compare solver requirements, transitive/native dependencies, license implications and reproducibility first |

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
- Inspect each repository's LICENSE and NOTICE files, transitive dependency licenses, release activity, advisories, and security policy; README badges alone are not legal clearance.
- Run dependency and static security scans on a pinned revision in an isolated environment.
- Build a threat model and data-flow diagram, including outbound network access, authentication, secrets, telemetry, and privilege boundaries.
- For analytics, prove read-only access and test that service outage, stale data, or malformed output cannot authorize or submit an order.
- For optimization, define the objective, constraints, solver tolerances, infeasibility handling, numerical stability tests, benchmark set, and out-of-sample validation.
- Submit any implementation as a small isolated PR with tests and exact-commit evidence. Do not merge automatically.
- Preserve `config/LIVE_LOCK.yaml`: `live_trading_enabled: false`, `FINAL_EXECUTION_AUTHORIZATION: false`, and `LIVE_EXECUTION: BLOCKED` until all existing independent release gates are satisfied.

## Scope limitations

This is a README-level capability triage based on the repositories' current default-branch README files. It does not yet establish current release versions, license compatibility for the intended deployment, vulnerability status, build reproducibility, performance, or production readiness. No dependencies have been installed, no production services deployed, and no live trading enabled.
