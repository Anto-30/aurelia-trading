# Deriv read-only verification runbook

## Credential boundary

The broad `AURELIA Assurance` workflow runs on branch pushes and pull requests. It intentionally has **no production environment and no credential references**. Do not reintroduce production secrets into that job.

Authenticated checks are isolated in `.github/workflows/deriv-readonly-verification.yml`. It accepts manual dispatch only and its job runs only when the selected ref is `main`. The `production` GitHub Environment should require an independent reviewer and restrict allowed branches to `main` before credentials are added or this workflow is dispatched. Workflow code and all changed scripts should be reviewed before running it.

## Required GitHub configuration

Configure these in the GitHub repository or `production` Environment settings, not in source, issue comments, commits, workflow logs, or `vars.DERIV_AUTH_MODE`:

- Actions **variable** `DERIV_AUTH_MODE`: exactly `pat` or `oauth`. It is normalized to an allowlisted enum before entering the job environment. Any other content is treated as invalid and blocks the run.
- Actions **secret** `DERIV_AUTH_TOKEN` or `DERIV_PAT`: supported authentication token.
- Actions **secret** `DERIV_APP_ID`: required for `pat` mode.
- Actions **secret** `DERIV_EXPECTED_LOGINID` or `DERIV_AUTHORIZED_ACCOUNT_ID`: expected account binding.
- Actions **secret** `DERIV_EXPECTED_CURRENCY`: currently must be `USD`.

Do not paste token values into ChatGPT or put a multi-line export script in the `DERIV_AUTH_MODE` variable. If a token was ever stored in that variable, treat it as potentially exposed: remove it from the variable, rotate/revoke that token at its issuer, update the relevant GitHub secret, and review historical workflow logs for exposure.

## What the manual workflow does

The workflow performs authenticated account binding and balance reads, a read-only broker statement/portfolio check, and a constrained `VERIFY_ONLY` control-chain check. The lifecycle check may request a proposal quote, but its verify-only branch does not call the execution method. It must report zero submitted orders and no capital movement. It does not authorize live trading.

Raw evidence files include account-level values and remain only in the ephemeral runner's private temporary directory. The workflow uploads only a sanitized summary containing checks and hashes; it omits login IDs, balances, symbols, proposal/intent IDs, contract IDs, and transaction rows. If prerequisites fail, the workflow stops before broker requests.

## What this does not certify

A successful read-only verification does not replace:
- a checksummed historical Deriv dataset with exact coverage and market-symbol provenance;
- a verified contract-aware costs/payout ledger and matched four-model results;
- an untouched, sealed final three-month OOS result after all model choices are frozen;
- the independently supervised 3,600-second non-production soak and recovery matrix;
- independent release review and all repository certification evidence.

Missing evidence remains `NOT_READY`; no script in this workflow changes `config/LIVE_LOCK.yaml`, authorizes capital, or submits a live order.
