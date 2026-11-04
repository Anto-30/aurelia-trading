# AURELIA research CI credential and environment boundary

## Workflow split

`aurelia-assurance.yml` is limited to pushes and pull requests targeting canonical `main`. Its general `assurance` job is secret-free and does not bind the production environment.

The optional `protected-deriv-evidence` job is separate. It can run only for a push to `refs/heads/main`, after the assurance job, and only when all three repository attestations are explicitly true:

- `AURELIA_PRIVILEGED_CREDENTIAL_JOBS_ENABLED`
- `AURELIA_MAIN_BRANCH_PROTECTION_VERIFIED`
- `AURELIA_PRODUCTION_ENVIRONMENT_REVIEWER_GATE_VERIFIED`

The job binds the protected `production` environment. Pull requests and feature-branch pushes cannot run it.

## Research CI

`aurelia-research-ci.yml` runs on non-main branch pushes and pull requests to main. It has `contents: read` permission, no production environment, and no `secrets.*` references. It runs compile/static checks, unit suites, container build, public Deriv market-data transport, readiness, and the fail-closed release-gate check.

## Environment isolation

The non-production-soak flags are scoped only to the health-probe step. They must not be job-wide: runtime tests deliberately override selected flags to exercise continuous authenticated-startup failure paths. A job-wide `AURELIA_NON_PRODUCTION_SOAK=true` leaked into those tests and caused the startup validator to reject the test before it reached the intended authentication-probe assertion.

The regression test `test_nonproduction_soak_flags_are_scoped_to_health_probe` enforces this boundary.

## Release constraints

- This workflow split does not authorize trading.
- Keep `config/LIVE_LOCK.yaml` fail-closed.
- Keep all third-party ontology/agent services research-only.
- Never pass Deriv credentials to feature-branch or PR jobs.
- The protected Deriv job is verification-only and must not submit orders.
