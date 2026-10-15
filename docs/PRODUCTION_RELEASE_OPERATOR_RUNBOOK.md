# AURELIA Production Release Operator Runbook

**Status:** blocked pending real operator configuration and qualification evidence  
**Canonical repository:** `Anto-30/aurelia-trading`  
**Required default:** `VERIFY_ONLY`  
**Live release:** not authorized by this runbook

This runbook records the operator actions that cannot be completed by source-code changes alone. Never put credentials in commits, issues, workflow artifacts, chat, or command-line arguments that may be logged.

## 1. Preserve the capital gate

Before provisioning, verify that `config/LIVE_LOCK.yaml` still contains:

- `live_trading_enabled: false`
- `FINAL_EXECUTION_AUTHORIZATION: false`
- `LIVE_EXECUTION: BLOCKED`
- `capital_plane_mode: VERIFY_ONLY`

Do not change these values to make a workflow pass. A green CI run or public market-data probe is not authorization for real orders.

## 2. Configure the protected GitHub Actions environment

In the repository settings, open **Settings → Environments → production**. Configure the following as environment secrets unless otherwise stated. Restrict deployment reviewers and branch access according to the repository's governance policy.

### Deriv account evidence

Required for the currently supported USD Options configuration:

- `DERIV_AUTH_TOKEN` (or the supported legacy alias `DERIV_PAT`): valid credential for the intended real account.
- `DERIV_APP_ID`: required when `DERIV_AUTH_MODE=pat`.
- `DERIV_EXPECTED_LOGINID` (or `DERIV_AUTHORIZED_ACCOUNT_ID`): the exact account login ID independently verified from Deriv.
- `DERIV_EXPECTED_CURRENCY`: must match the account's actual currency; the current configuration supports `USD` only.
- `DERIV_AUTH_MODE`: set as an environment variable to `pat` for the PAT flow currently used by the workflows, unless the reviewed implementation and credential type explicitly require another supported mode.

Do not infer the account ID or currency from a label, balance screenshot, or prior run. Confirm both through authenticated Deriv account evidence. Never paste a token into a GitHub issue or commit.

The repository script `scripts/provision_deriv_github_secrets.sh` is the supported provisioning helper for the Deriv credential set. Inspect it first, run it only in a trusted terminal where GitHub CLI is authenticated to the correct repository, and provide values through a secure prompt or secret manager. Do not use shell tracing (`set -x`) or echo secret values. The script is expected to fail closed when required values are missing or inconsistent.

### Persistent production host

Configure these protected environment secrets:

- `AURELIA_HOST`
- `AURELIA_USER`
- `AURELIA_SSH_KEY`
- `AURELIA_KNOWN_HOSTS`
- `AURELIA_ATTESTATION_SIGNING_KEY`
- `AURELIA_OPERATOR_RESET_SIGNING_KEY` (minimum 32 non-whitespace characters, generated and stored securely)

The host must be a user-controlled, persistent Linux host with Docker and the required runtime prerequisites. Validate the SSH host key through an independent trusted channel before populating `AURELIA_KNOWN_HOSTS`; do not trust an unverified `ssh-keyscan` result. Use a dedicated least-privilege deployment account and a key scoped to this host.

Keep Deriv credentials in the protected runtime secret store as required by the deployment architecture. Do not bake them into an image, repository file, or deployment archive.

## 3. Prove prerequisites without placing capital at risk

After configuration, run the secret-presence report and inspect only its boolean output. Required outcomes include:

- `DERIV_AUTH_CONFIGURED=true`
- `AURELIA_DEPLOYMENT_SECRET_STORE_CONFIGURED=true`
- `AURELIA_PRODUCTION_PREREQUISITES_CONFIGURED=true`

If any outcome is false, stop and correct the missing configuration. A successful secret-presence report only proves that configuration is present; it does not prove credentials are valid or the account is eligible.

Run the deployment workflow in **VERIFY_ONLY** mode against the exact reviewed `main` commit. Require all of the following:

1. Strict SSH host-key verification succeeds.
2. The persistent host deploys and reports healthy runtime status.
3. Authenticated Deriv session evidence identifies the expected real account and currency.
4. Read-only broker-account evidence confirms current balance and account identity.
5. The verify-only transaction lifecycle completes without submitting a real order and proves the expected fail-closed behavior.
6. Evidence files are uploaded and reviewed; secrets are not included in artifacts.

Do not select `LIVE` mode to test connectivity. Do not call a public market-data response authenticated account evidence.

## 4. Complete the runtime and strategy gates

- Wait for the non-production 3,600-second soak to complete. Review the final conclusion and its evidence artifact; elapsed time alone is not a pass.
- For the production runtime, verify restart recovery, persistent state, heartbeat/lease behavior, kill-switch behavior, and stale/unknown broker-state blocking.
- For any eventual broker transaction qualification, use only the reviewed verify-only lifecycle until the release authority has accepted all prerequisites. Reconcile broker-confirmed transaction/fill state against the ledger; never infer a fill from a request acknowledgement.
- Keep `R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0` disqualified after its negative quoted net economics result. Archive that sealed campaign and conduct any next evaluation on a new, prospectively sealed sample with realized cost assumptions, calibration and uncertainty analysis.
- Keep S7, S6, S3, CRT and `MICRO_SCALP_R100_TICK_MOM` blocked until the actual canonical implementation, instrument mapping/specification, timeframe rules, OOS/walk-forward, calibration, economics, robustness, forward test, runtime soak and independent reviewer evidence are linked in the strategy registry.

### Branch ruleset correction (repository-admin action; verified 2026-10-11)

The repository's `Execution` ruleset (ID `24423833`, [settings page](https://github.com/Anto-30/aurelia-trading/rules/24423833)) was observed with **enforcement disabled**, an empty `required_status_checks` list, empty ref include/exclude patterns, and multiple integration bypass actors set to `always`. Do not treat this as active branch protection.

From a repository-owner/admin browser session, correct the ruleset before authorizing a release:

1. Set enforcement to **Active** and scope the release-protection ruleset explicitly to `refs/heads/main`.
2. Configure the strict required check contexts observed passing on the reviewed PR head `a4de7b933d0d4609f471174f02e805c5bf213fd1`: `assurance`, `federation-audit`, and `continuity`. Reconfirm these exact names on a fresh pull request before saving. Do not require the scheduled heartbeat, one-hour soak, or prospective collector as PR checks unless those workflows are deliberately changed to run on every PR.
3. Require pull-request review and resolved review conversations where the repository's maintainer model supports independent review. Do not use self-approval as a substitute for independent review.
4. Remove force-push/deletion allowances and review every bypass actor. Remove any `always` bypass not explicitly justified by the release-governance policy; do not enable the current empty ruleset unchanged.
5. After saving, reread the ruleset and verify it is active, scoped to `main`, has non-empty required checks, and has only approved bypass actors. Then open a fresh test PR and verify the required checks actually block merge when one fails.

The current connected GitHub integration can read the ruleset but receives HTTP 403 on the branch-protection administration endpoint, so this settings change must be made by an authorized repository administrator. A documentation change or green CI run does not change the GitHub ruleset.

## 5. Release decision

A release can be considered only when the deterministic gate validates every required evidence item at the exact candidate source revision and strategy hash. Unknown, stale, missing, contradictory or failed evidence is a rejection, not a warning.

Until then, preserve:

`live_trading_enabled=false`  
`FINAL_EXECUTION_AUTHORIZATION=false`  
`LIVE_EXECUTION=BLOCKED`  
`capital_plane_mode=VERIFY_ONLY`

This runbook does not authorize live trading, change the live lock, or promise profitability.
