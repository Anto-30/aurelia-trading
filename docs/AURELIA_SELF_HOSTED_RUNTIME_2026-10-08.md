# AURELIA Self-Hosted Persistent Runtime — 2026-10-08

## Deployment decision

AURELIA's active production deployment path is now provider-neutral self-hosting on a user-controlled Linux host running Docker.

The previous Railway deployment surface was removed from the active repository path because the Railway account requires a paid plan after its trial expired. Railway is no longer a runtime dependency, deployment dependency, or release-gate dependency for AURELIA.

The implementation supplies compute only. It does not replace AURELIA's runtime, capital plane, Risk Warden, Execution Firewall, Deriv adapter, idempotency, fencing, ledger, reconciliation, watchdog, or LIVE_LOCK.

## Runtime contract

The deployment unit is the exact Git commit from `main`.

GitHub Actions:

1. Checks out the exact source revision.
2. Requires a completed successful AURELIA Assurance run for that exact commit.
3. Verifies the checked-in `config/LIVE_LOCK.yaml`.
4. Archives the exact commit with `git archive`.
5. Transfers the archive through strict SSH host-key verification.
6. Installs the exact release under `/opt/aurelia/releases/<commit>`.
7. Builds the existing Docker image and runs `python -m runtime.main`.
8. Binds persistent runtime state from `/var/lib/aurelia` into the container.
9. Uses Docker `--restart unless-stopped`.
10. Verifies the health endpoint and fail-closed capital state.
11. Records source lineage at `/var/lib/aurelia/DEPLOYED_SOURCE_SHA` and `DEPLOYMENT_LINEAGE.json`.

The active contract is defined in:

- `config/deployment_policy.json`
- `.github/workflows/self-hosted-runtime-deploy.yml`
- `scripts/deploy/bootstrap_and_deploy.sh`

## Provider policy

The application does not depend on a provider-specific trial or promotional entitlement.

Any compatible user-controlled Linux host can be used, including a dedicated VM or an OCI Always Free-compatible host. OCI Always Free is an infrastructure option, not an AURELIA dependency.

No cloud platform can be guaranteed to keep a free service indefinitely. The important design property is that provider policy is no longer coupled to the AURELIA release path: the same runtime can be moved to another host without changing trading logic.

## Secret handling

Runtime secrets are stored on the host in `/etc/aurelia/aurelia.env` with restrictive file permissions. GitHub Actions receives only protected transport secrets required to reach the host.

Deriv tokens, App IDs, OTPs, account credentials, and other secrets must never be committed, printed, included in artifacts, or placed in source archives outside the protected runtime secret store.

## Capital safety

Infrastructure deployment never grants capital authority.

VERIFY_ONLY is the default deployment mode and requires:

- `live_trading_enabled: false`
- `FINAL_EXECUTION_AUTHORIZATION: false`
- `LIVE_EXECUTION: BLOCKED`
- `capital_plane_mode: VERIFY_ONLY`

LIVE deployment is accepted only when the exact checked-in `LIVE_LOCK.yaml` already contains the corresponding LIVE authorization fields. The deployment workflow cannot create or mutate that authorization.

Even a healthy persistent runtime is not evidence that the strategy is qualified or that live trading is authorized.

## Remaining release gates

Deployment infrastructure is now separated from the remaining trading qualification work. Live release still requires genuine:

- authenticated Deriv session evidence;
- broker-confirmed transaction/fill lifecycle;
- post-transaction ledger and reconciliation evidence;
- production runtime soak and recovery evidence;
- multi-day prospective OOS qualification;
- probability calibration and drift validation;
- net execution economics qualification;
- deterministic release-evidence gate approval;
- explicit checked-in LIVE_LOCK authorization.

Until those conditions are independently evidenced, `FINAL_EXECUTION_AUTHORIZATION=false` and `LIVE_EXECUTION=BLOCKED` remain the required state.

## Current external-host status

The repository now contains the host deployment contract, but no user-controlled host is connected to the current engineering session. Therefore no claim is made here that a persistent production worker has already been deployed.

The next deployment requires protected GitHub Actions secrets for the chosen Linux host:

- `AURELIA_HOST`
- `AURELIA_USER`
- `AURELIA_SSH_KEY`
- `AURELIA_KNOWN_HOSTS`

Those values belong in the protected secret store, not in Git.

## Historical Railway evidence

Older operational snapshots may still mention Railway because they are immutable historical records. They are retained for auditability and are not active deployment requirements.

Current deployment source of truth is the provider-neutral self-hosted contract above.
