# Production Secret Boundary Remediation — 2026-10-14

## Scope

This change moves general CI away from production environment secrets and adds main-ref guards to workflows whose jobs read protected Deriv, deployment, or WhatsApp credentials. It does **not** change GitHub organization/repository settings and is not sufficient by itself to prove an environment is protected.

## Code changes in this branch

- `.github/workflows/aurelia-assurance.yml` is now unprivileged CI: no `environment: production`, no credential expressions, and no authenticated broker steps. It continues to check out source, run tests/static audit, query only public Deriv market data, generate a blocked readiness report, exercise a non-production health probe, and assert the live release gate stays blocked.
- Added an explicit `github.ref == 'refs/heads/main'` job condition to production-environment jobs in `deriv-auth-evidence.yml`, `deriv-session-verification.yml`, `deriv-verify-only-lifecycle.yml`, `self-hosted-runtime-deploy.yml`, and `secret-presence-report.yml`.
- Added the same condition to secret-bearing jobs in `aurelia-free-runtime.yml`, including its WhatsApp smoke job which uses repository-level secrets rather than the production environment.
- Added `tests/test_production_secret_boundary.py` to prevent reintroduction of secret-bearing general assurance and require main-ref guards on the listed sensitive jobs.

## Critical residual controls requiring GitHub administrator

The repository `Execution` ruleset was observed as `enforcement=disabled`, with no required checks/deployments and seven integration bypass actors configured as `always`. Classic branch-protection settings and production environment reviewer/branch restrictions were not readable through the current integration (classic protection returned 403; environment settings are not exposed by the current connector).

The workflow guard prevents the current version of these jobs from running when dispatched from a non-main ref, but it is not a substitute for protected environment settings if someone can dispatch a modified workflow from their own branch. An authorized GitHub administrator must:
1. Enable and scope the Execution ruleset to `refs/heads/main`.
2. Configure explicit required checks with strict up-to-date requirements and independent human approval.
3. Remove unnecessary always-bypass integrations; verify the final bypass policy.
4. Restrict the `production` environment to protected `main`, enable required independent reviewers, and confirm branch restrictions from the settings API/UI.
5. Demonstrate that a branch/fork PR cannot access production secrets, even when the PR modifies a workflow file.

## Verification semantics

The test file checks the textual workflow boundary and should run as part of the assurance suite. GitHub Actions on this draft branch must still complete successfully before review. No real Deriv transaction is authorized by this patch. Keep `config/LIVE_LOCK.yaml` unchanged and fail-closed: `live_trading_enabled=false`, `FINAL_EXECUTION_AUTHORIZATION=false`, `LIVE_EXECUTION=BLOCKED`, `capital_plane_mode=VERIFY_ONLY`.

No production credentials should be provisioned or copied into CI until the administrator settings above are verified.