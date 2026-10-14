# Google Secret Manager provisioning for AURELIA (VERIFY_ONLY)

This runbook describes an out-of-GitHub credential path. It does not authorize live trading and must not be used to unlock capital execution.

## 1. Google Cloud setup

1. In the Google Cloud Console, select or create a dedicated project for AURELIA production.
2. Enable the Secret Manager API.
3. Use a dedicated production runtime identity on Cloud Run or Compute Engine. Prefer attached service identity / Application Default Credentials; do not create a long-lived service-account key.
4. Create one secret named `deriv-auth-token` and add the Deriv token as a secret version directly in the authenticated Google Cloud Console. Do not download it into ChatGPT, put it in a repository, or upload it as a GitHub artifact.
5. If using a Deriv PAT, create an application in Deriv and store its app ID as a separate protected secret if organizational policy requires it; the existing AURELIA verifier currently expects `DERIV_APP_ID` in runtime configuration for PAT mode. If you store it in Secret Manager, create `deriv-app-id` as another secret.
6. Grant the runtime identity `roles/secretmanager.secretAccessor` on only the required secret resources. Do not grant project-wide access if secret-level IAM bindings will work.
7. Pin explicit numeric secret versions in the service configuration. This implementation deliberately rejects the `latest` alias for the protected secret lookup.

## 2. Runtime configuration

Set these non-secret configuration values on the dedicated worker:

- `AURELIA_SECRET_PROVIDER=google_secret_manager`
- `AURELIA_GCP_PROJECT_ID=<your dedicated Google Cloud project ID>`
- `AURELIA_GSM_SECRET_ID_DERIV_AUTH_TOKEN=deriv-auth-token`
- `AURELIA_GSM_SECRET_VERSION_DERIV_AUTH_TOKEN=<numeric version ID>`
- `AURELIA_DEPLOYMENT_MODE=VERIFY_ONLY`
- `FINAL_EXECUTION_AUTHORIZATION=false`
- `LIVE_EXECUTION=BLOCKED`
- `AURELIA_AUTONOMOUS_LOOP=false`
- `AURELIA_VERIFY_DERIV_AUTH=true`
- `DERIV_AUTH_MODE=pat` (or `oauth` if the configured authentication flow supports it)
- `DERIV_EXPECTED_LOGINID=<expected account ID>`
- `DERIV_EXPECTED_CURRENCY=<expected currency supported by the verifier>`
- `DERIV_ENVIRONMENT=real` only if the dedicated intended account is the real account; this is an identity binding, not permission to trade.

The verifier also needs the Deriv application ID for PAT mode. If it is stored in Secret Manager, set `AURELIA_GSM_SECRET_ID_DERIV_APP_ID` and `AURELIA_GSM_SECRET_VERSION_DERIV_APP_ID` to its secret ID and numeric version. The provider's protected-name allowlist includes `DERIV_APP_ID`.

Do not set the token in the environment when Google Secret Manager is selected. For protected credential names, this provider does not fall back to environment variables if Secret Manager configuration or access fails.

## 3. Verification

1. Deploy a single isolated worker revision with no order submission permission and no autonomous loop.
2. Run `scripts/deriv_auth_prerequisites.py`, `scripts/verify_deriv_session.py`, `scripts/verify_deriv_broker_evidence.py`, and `scripts/verify_deriv_transaction_lifecycle.py` in VERIFY_ONLY mode.
3. Keep raw broker evidence on the protected runtime. Export only redacted evidence summaries and source/config hashes; never upload account IDs, balance payloads, proposal/intent data, or transaction identifiers.
4. Confirm the authenticated account and currency match the intended dedicated account, evidence is fresh, the broker-reported minimum stake and step are verified, and no order submission/capital movement occurred.
5. Disable or revoke any exposed token, rotate it immediately if it was ever placed in an ordinary Drive file shared beyond the account owner, and remove unintended sharing. Keep the original Drive file private until the credential is migrated, then remove the old copy from Drive and trash where policy permits. Review Drive sharing and access logs if exposure is possible.

## 4. Release boundary

Google Secret Manager only solves secret storage and retrieval. It does not satisfy branch protection, independent review, strategy-specific prospective OOS qualification, calibration, realized costs, broker minimum-stake affordability, persistent production runtime, or the production 3,600-second soak. Keep `config/LIVE_LOCK.yaml` fail-closed and do not submit live orders until every release gate has current, commit-bound evidence and the authorized independent release process approves it.

## References

- Google Cloud Secret Manager create/access: https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets
- Google Cloud Secret Manager best practices: https://cloud.google.com/secret-manager/docs/best-practices
- Secret-level IAM: https://cloud.google.com/secret-manager/docs/manage-access-to-secrets
