# AURELIA deployment-gate remediation — 2026-10-24

## Disposition

PR #198 remains draft and unmerged. Live execution remains blocked. This change separates pull-request CI from authenticated, read-only Deriv verification; it does not authorize orders or grant capital authority.

## Finding

Before this change, `.github/workflows/aurelia-assurance.yml` ran on every push and pull request while assigning the `production` environment to the same job. That job combined tests/builds with authenticated broker verification and exposed environment secrets to several Python verification steps. The authenticated session and broker-evidence scripts print account identifiers, balance values, and transaction identifiers to standard output, so raw verifier output must not be emitted to Actions logs.

## Changes in this PR

1. `.github/workflows/aurelia-assurance.yml` is Tier 1 secret-free CI: no `production` environment, no `secrets.*` references, and checkout credentials are not persisted. It retains compilation, tests, static checks, isolated container build, public market-data transport check, health check, and fail-closed release-gate checks.
2. `.github/workflows/aurelia-protected-deriv-verification.yml` is Tier 2, manually triggered, requires explicit read-only confirmation, and fails closed unless the selected ref is `main`. It uses the protected `production` environment and injects broker credentials only into the two designated read-only verification steps.
3. The protected workflow captures raw verifier output in the ephemeral runner's temporary directory and prints only allowlisted status/reason lines. Raw stdout is not uploaded. Successful evidence JSON is retained as a private Actions artifact for three days.

## Security boundaries and caveats

- Tier 2 reads authenticated account/session, balance, statement, and portfolio information. It does not call the transaction-lifecycle verifier, proposal/buy methods, or order-submission path.
- The authenticated evidence JSON contains account and transaction-level financial information. It is uploaded only to the repository's Actions artifact store with a three-day retention period; repository/artifact access must remain restricted to authorized reviewers.
- The workflow is available for dispatch from the default branch after the change is merged. It must not be dispatched from a pull-request branch. The job-level ref check enforces this even if another branch is selected.
- The connected GitHub identity could not approve the pending `production` environment gate. No approval is claimed here. An authorized environment reviewer must review the workflow change and approve any later protected read-only run.
- CI run success is not trading-readiness approval. No authenticated evidence, security scan report, SBOM, independent review, MT5/API reconciliation report, frozen baseline metrics, out-of-sample performance, or 3,600-second soak result is claimed unless produced by a real run and reviewed.
- The separate MT5/API reconciliation and frozen baseline evidence remain outstanding. No historical data or performance metrics have been fabricated.
- `config/LIVE_LOCK.yaml` remains fail-closed: `live_trading_enabled: false`, `LIVE_EXECUTION: BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION: false`, and `capital_plane_mode: VERIFY_ONLY`.

## Evidence required before release review

- Exact-head Tier 1 CI result and downloadable public transport evidence.
- Successful Tier 2 read-only verification artifact, produced only after authorized environment approval.
- Security/dependency scan reports and SBOM from a reproducible isolated build.
- MT5-versus-Deriv API reconciliation report with source/timeframe/UTC interval/hash provenance.
- Frozen baseline and sealed out-of-sample metrics, cost-adjusted trade ledgers, recovery telemetry, and a completed 3,600-second soak.
- Independent human review of the code, evidence lineage, and release gate.

Until every required gate is satisfied, keep PR #198 draft/unmerged and keep live execution disabled.
