# Legacy Authentication Security Audit

**Audit date:** 2026-11-06  
**Baseline:** `main` at `d04564aca0648201feff0326fe9af0fbcee92e94`  
**Disposition:** Remediation implemented on a review branch; exact-head CI and independent human review remain required before integration.

## Executive finding

The baseline contained two scheduled workflow paths that mapped Deriv account credentials into GitHub Actions job environments:

| Workflow | Trigger | Credential-bearing behavior | Finding |
|---|---|---|---|
| `.github/workflows/aurelia-free-runtime.yml` | Every 15 minutes, push, manual | Two jobs mapped `DERIV_AUTH_TOKEN || DERIV_PAT`, app ID and account binding into job environments | Unnecessary scheduled credential exposure |
| `.github/workflows/deriv-auth-evidence.yml` | Every 6 hours, manual | Production environment mapped Deriv token/PAT, app ID and account binding into the job environment | Unnecessary scheduled credential exposure |

The baseline `.github/workflows/aurelia-assurance.yml` also ran on branch pushes and pull requests while declaring the `production` environment and mapping Deriv account-secret references into the assurance job. It was not a scheduled workflow, but it mixed general CI with the authenticated account plane.

The workflow content inspected used GitHub secret references rather than literal credential values. This repository-level review is not a general scan of historical Actions logs, GitHub audit logs, Deriv account activity, or external copies. It therefore does **not** prove that a credential was or was not exfiltrated.

### Additional live CI observation (2026-11-06)

The legacy main-branch `AURELIA Assurance` workflow was observed executing for PR #281. Its job log recorded `DERIV_AUTH_CONFIGURED=true`, `DERIV_AUTH_MODE=pat`, and the presence of masked Deriv credential/account environment values during the PR-triggered job. The authenticated session verification step then failed with the sanitized reason class `ValueError`; the underlying exception detail was not emitted. The same run reported `LIVE_EXECUTION=BLOCKED` and `DERIV_ORDERS_SUBMITTED=0`. The inspected log does not show a raw credential value, so this is evidence of credential injection into a PR-triggered job, not proof that a credential value was exposed in the log or exfiltrated.

The remediation branch's replacement Assurance workflow was subsequently observed with `DERIV_AUTH_CONFIGURED=false` and no Deriv credentials mapped into the job. Its account-evidence status remained blocked. The test suite's fixture output that includes sample `DERIV_AUTH_SESSION=VERIFIED` lines is test output and is not being counted as live broker evidence.

## Scope and method

- Enumerated all 15 workflow files present in the baseline repository tree.
- Inspected workflow triggers, job environments, Deriv credential references, and declared GitHub Actions token permissions.
- Distinguished scheduled automation from manual, environment-protected operator workflows.
- Added `scripts/audit_legacy_auth.sh` and a dedicated GitHub Actions workflow so the static checks run against the actual branch content.
- The executable audit reports finding codes and file/line locations only; it does not print workflow contents or secret values.
- The static detector is intentionally limited: it detects known token-like literal formats, direct secret references in scheduled/PR-triggered workflow definitions, and broad token permissions. It is not a general-purpose secret scanner and does not prove absence of indirect variable aliases, runtime data-flow leaks, or historical exposure.

## Findings requiring separate treatment

1. **Scheduled credential use:** the two scheduled paths above were the immediate priority.
2. **General CI credential scope:** the baseline Assurance workflow combined pull-request CI with production-scoped account credentials. The remediation replaces it with the credential-free assurance version already exercised by the PR #279 integration candidate.
3. **Manual protected workflows:** `deriv-session-verification.yml`, `deriv-verify-only-lifecycle.yml`, `secret-presence-report.yml`, and `self-hosted-runtime-deploy.yml` still contain operator-dispatched secret references in the baseline. They are not scheduled by their current triggers and are not silently reclassified as safe. They require protected-environment reviewer controls, least-privilege review, and a separate decision about whether their Deriv account operations are compatible with the documented OAuth `trade` scope.
4. **Credential rotation:** no credential values were read or changed. No evidence from this static source review establishes that a live credential was exfiltrated. Rotation must be performed through Deriv and the protected GitHub environment after identifying the affected credential and replacement plan; do not paste credential values into issues, commits, logs, or chat. If independent evidence indicates exposure, revoke the old credential promptly and update all dependent consumers with a tested replacement.
5. **Permission scope:** the directly reviewed baseline workflows declared `contents: read`; the source review did not identify a `write-all` declaration in those workflows. The new executable audit checks for broad declarations across the workflow directory.

## Remediation in this change

- Replace `aurelia-free-runtime.yml` with the PR #279 credential-isolated form: public Deriv research remains unauthenticated; account-evidence checks remain blocked without injecting account credentials; live execution remains blocked.
- Replace `aurelia-assurance.yml` with the PR #279 credential-free assurance form so pull-request and general CI jobs do not load Deriv account secrets.
- Remove the six-hour schedule from `deriv-auth-evidence.yml` and convert it into a manual, no-credential prerequisite-status check. It records account evidence as blocked because a genuinely read-only account scope is not established.
- Add a static audit script and CI workflow. The audit fails on scheduled Deriv credential injection, pull-request Deriv credential injection, known credential-like literals, and broad write-all permissions. Manual protected credential workflows are reported for review rather than being misrepresented as automatically safe. Dynamic logging paths remain subject to human review.
- Preserve `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, and `capital_plane_mode=VERIFY_ONLY`.

## Verification status

- Baseline workflow inventory and configuration review: completed through the connected GitHub repository interface.
- First static-audit run failed because its overly broad output-pattern check treated a fail-closed message naming a missing credential variable as if it printed the credential value. The detector was corrected to avoid that false positive; it intentionally does not claim comprehensive runtime data-flow analysis.
- First remediation Assurance run failed before the regression suite because its command referenced a nonexistent `test_deriv_auth_gate.py` test file. The workflow now invokes the existing prerequisite and evidence-contract test files.
- Latest PR #280 synchronized merge-ref CI completed successfully on source head `399421633c1458e0ec6e9bf12bc6b4dac3b15630`: Static Authentication Audit, AURELIA Assurance, Agent Federation Audit, and Agent Continuity Watchdog all passed. The static audit scanned 17 workflow files and reported 0 scheduled Deriv credential-bearing workflows, 0 pull-request Deriv credential-bearing workflows, and 4 manual credential-bearing workflows requiring human review.
- The same exact-head run validated the daily oversight report generator and smoke-tested it against read-only GitHub APIs. The AURELIA Assurance run passed 80 research tests, 5 auth-prerequisite tests, 3 auth-evidence contract tests, 61 assurance tests, 309 runtime tests, 12 hardening tests, and a clean runtime container build. The public Deriv probe found 89 active symbols. Account evidence remained `BLOCKED` because no genuinely read-only account scope is available; readiness remained blocked and the live release gate remained `BLOCKED`.
- CI green is not an approval to merge or evidence of production deployment. PR #280 still requires independent human security review.
- Historical Actions-log and GitHub audit-log review: not performed by this repository-file audit.
- Deriv credential rotation/revocation: not performed; this source audit alone does not establish that exposure occurred.
- Main-branch workflows have not been changed by this pull request. The proposed file changes take effect only after review and merge. Until then, the two legacy schedules and the credential-bearing main Assurance job remain enabled unless separately disabled through GitHub Actions. A disable-workflow UI operation was started but no terminal confirmation has yet been received; do not assume those workflows are disabled.
- Production deployment, account verification, proposal requests and order submission: not performed.

**Completion rule:** automated remediation checks passed on the recorded PR #280 source head. The overall security review remains OPEN until an independent human reviewer examines the remaining manual protected workflows and approves or rejects the PR. Main-branch mitigation is not complete until the updated workflow definitions are integrated or the old workflows are independently confirmed disabled.
