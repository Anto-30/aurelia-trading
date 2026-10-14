# External Repository Validation and Integration Gate

**Applies to:** `Anto-30/aurelia-trading`
**Status:** Planning and acceptance criteria only; no candidate dependencies installed.
**Security invariant:** no candidate repository, database, optimizer, dashboard, or agent tool receives capital authority. `config/LIVE_LOCK.yaml` remains fail-closed.

## Decision from the current evidence

The current AURELIA `pyproject.toml` declares only `websockets>=17.1,<18` as a base runtime dependency, with PyTorch under the optional `ml` extra. `requirements.txt` pins websockets 17.1. No current manifest evidence establishes that ClickHouse or convex optimization is required. Therefore, adding ClickHouse Connect, CVXPY, CVXOPT, Convex, DataEase, or the Superset workspace to production dependencies is not justified yet.

The immediate next step is a sandboxed, research-only proof of value using synthetic/sanitized data and no broker credentials. The following are gates, not claims that testing has already occurred.

## Gate A — CVXPY offline optimization experiment

### Scope
- Prototype in an isolated research environment or separate temporary branch; do not add it to base runtime dependencies.
- Choose one explicit problem before coding: e.g. minimize variance subject to long-only weights, fully invested sum of weights, and per-asset exposure limits. Do not optimize trading strategy parameters on the same data used for final evaluation.
- Inputs must be sanitized historical return samples with explicit time boundaries and no future information.

### Required tests
1. **Deterministic fixture:** fixed synthetic covariance and expected-return inputs yield feasible weights within stated tolerances.
2. **Constraint invariants:** weights respect non-negativity, sum-to-one, and all exposure bounds within numerical tolerance.
3. **Infeasibility:** conflicting constraints produce an explicit rejected/infeasible result; no fallback silently relaxes constraints.
4. **Numerical stability:** test singular/near-singular covariance, NaNs, infinities, zero observations, and extreme scaling; invalid inputs fail closed.
5. **Solver state:** record solver name/version, status, objective, residuals, tolerances, input hash, and environment lock.
6. **No-lookahead:** fit/calibrate only on the training window; evaluate only on a later untouched out-of-sample window; use walk-forward splits where relevant.
7. **Baseline comparison:** compare against equal-weight and existing allocation baseline; include turnover, concentration, drawdown, and transaction-cost assumptions where meaningful.
8. **Reproducibility:** rerun from pinned environment and immutable input fixture; results must match within documented tolerances.
9. **Authority isolation:** optimizer output is advisory data only. No API or call path from the experiment may submit orders, write to the ledger, alter risk settings, or modify live authorization.

### Acceptance criteria
- Mathematical formulation reviewed by a person other than the implementer.
- All tests pass; solver failures and missing values reject, not silently coerce.
- Out-of-sample improvement is measured against a baseline and is not assumed from in-sample objective values.
- Dependency license and transitive dependency inventory are reviewed.
- No production dependency change until a documented need and measured value are approved.

## Gate B — ClickHouse Connect read-only analytics experiment

### Scope
- Prototype only if measurements show existing data storage/query patterns are a bottleneck.
- Use synthetic or sanitized events; do not send broker credentials, account identifiers, personal data, or raw secret-bearing logs to ClickHouse.
- Keep ClickHouse outside the capital/execution plane.

### Required tests
1. **Data contract:** define immutable event schema, UTC event/ingestion timestamps, schema version, strategy ID/version, instrument, data provenance, and null semantics.
2. **Idempotency:** repeated event delivery does not inflate trade counts, P&L, or metric aggregates.
3. **Ordering and late data:** out-of-order events and corrections are reconciled without silently rewriting authoritative ledger records.
4. **Read-only access:** credentials have SELECT-only permissions on analytics views; verify INSERT/ALTER/DELETE are denied for reporting credentials.
5. **Network isolation:** explicit allowlist, TLS verification, no unrestricted outbound access, and no credentials in URLs/logs.
6. **Freshness:** every dashboard/query exposes data freshness; stale or incomplete results are marked UNKNOWN and cannot feed execution decisions.
7. **Failure injection:** unavailable database, timeout, malformed rows, schema mismatch, partial result, and rate limiting must not stop the risk controls or enable execution.
8. **Performance:** compare p50/p95 latency, ingestion throughput, storage growth, and resource use against current baseline using a reproducible dataset and target workload.
9. **Retention and recovery:** define retention, backup/restore verification, access audit, deletion policy, and incident response.
10. **License/supply chain:** pin clickhouse-connect and server versions, inventory transitive dependencies, scan vulnerabilities, and record SBOM.

### Acceptance criteria
- Documented measurable performance or operational benefit versus current storage.
- Read-only permission tests and outage tests pass.
- No direct coupling from analytics service to authorization, stake sizing, execution, or ledger authority.
- No secrets or sensitive account information in analytical payloads.
- Security and operational owner approves the service boundary and cost/maintenance burden.

## Gate C — Other candidates

- **TypeScript:** adopt only if there is a defined TypeScript frontend/tooling need. Pin compiler version and run type-check/build tests; not a runtime trading dependency.
- **superset-sh/superset:** treat as a developer-workspace product, not Apache Superset BI. Evaluate ELv2 terms and agent workspace security before any workstation adoption.
- **DataEase:** no deployment until modified GPL terms and logo/copyright conditions are reviewed for the intended use, plus authentication/network isolation are tested.
- **Convex backend + convex-js:** no adoption until a concrete operator-portal use case, FSL terms, data residency, auth, retention, and failure model are approved. They cannot replace broker truth, the trade ledger, or capital-plane controls.
- **lutinglt/superset-zh:** do not adopt as new infrastructure because the upstream repository states it is no longer maintained.
- **CVXOPT:** defer unless a benchmark demonstrates a specific need that CVXPY's solver interfaces do not meet; review the complete license and native dependencies before packaging.

## Gate D — Release and review

For any future candidate integration:
1. Pin exact commit/version and hash all manifests/lock files.
2. Produce a dependency inventory/SBOM, license report, vulnerability scan, and secret scan.
3. Run static analysis and tests in an isolated CI job with least-privilege permissions and no production secrets.
4. Provide a threat model, data-flow diagram, rollback plan, operational owner, and measured benefit.
5. Obtain independent human review and exact-commit CI evidence.
6. Confirm live-lock hash and release-gate state remain unchanged.
7. Merge only after all required checks and branch protections pass; no auto-merge based on an agent's assertion.

## Current evidence state

- Read from current default branch: `pyproject.toml`, `requirements.txt`, `requirements-assurance.txt`, `AGENTS.md`, `config/LIVE_LOCK.yaml`, and `.github/workflows/aurelia-assurance.yml`.
- Added `.github/workflows/security-dependency-audit.yml` with read-only permissions and no production secrets, plus weekly Dependabot configuration and `SECURITY.md`.
- On commit `afea231931b4c1d76c0f2083cb8cb353b35d8bb6`, the isolated CVXPY and ClickHouse proof-of-concept workflow passed. The CVXPY test used a deterministic synthetic covariance matrix, enforced long-only/budget/concentration constraints, compared against equal-weight baseline, and rejected infeasible constraints and a non-PSD matrix. The ClickHouse test used an ephemeral server and synthetic events; SELECT succeeded, INSERT and ALTER were denied for the reporting user, and ReplacingMergeTree FINAL returned two logical events after a duplicate event was inserted.
- That successful POC run used CVXPY 1.7.3, ClickHouse Connect 0.9.2, and ClickHouse server 25.3. The workflow has since been updated to CVXPY 1.9.3, ClickHouse Connect 1.4.0, and ClickHouse server 26.8.21.10, with a pip-audit scan of the isolated POC environment. Validation of these newer pinned versions is pending on the latest branch head; the earlier success must not be misrepresented as proof of the newer set.
- The security audit reported no known vulnerabilities in the AURELIA `requirements.txt` dependency set on the successful run for commit `afea231931b4c1d76c0f2083cb8cb353b35d8bb6`. Bandit identified medium-severity findings involving URL schemes, `/tmp/aurelia` state paths, and health endpoint binding. They are tracked for separate runtime-hardening triage in issue #134. The workflow now fails on high-severity findings and preserves medium findings in the report.
- The existing assurance workflow's compile, static production acceptance audit, shell syntax checks, and research-plane tests passed on earlier observed PR runs; those runs were cancelled or still running after later commits. Latest-head AURELIA Assurance remains pending/in progress and must complete on the final commit before merge.
- The PR has no submitted independent review yet. GitHub API read of repository rulesets showed the existing `Execution` branch ruleset is `disabled` and has an empty required-status-check list. The branch-protection endpoint itself returned 403 to this connector, so a repository administrator must inspect and restore enforcement. See issue #133.
- A source-level audit of all nine upstream repositories, complete transitive SBOM and license compatibility review, and independent human review are still outstanding.
- Live trading remains blocked; no orders were placed and no candidate dependency was installed in AURELIA's runtime.

## Stop conditions

Stop and report the exact blocker if a license cannot be resolved, a critical/high vulnerability is untriaged, reproducibility fails, inputs are stale/invalid, an analytics service could affect execution authority, solver output violates constraints, protected secrets are unavailable, independent review is absent, or any change would weaken the live lock.
