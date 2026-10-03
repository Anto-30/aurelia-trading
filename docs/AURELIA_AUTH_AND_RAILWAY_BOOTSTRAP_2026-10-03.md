# AURELIA authenticated-session and Railway bootstrap

## Deriv

AURELIA now has a dedicated `DerivSessionManager` for authentication and session bootstrap only. It:

1. Uses a bearer credential supplied by the deployment secret store.
2. Retrieves the Options account inventory.
3. Requires an exact account, environment, and currency binding.
4. Requires an explicit login ID for any real-money session.
5. Requests a fresh short-lived OTP URL immediately before connection.
6. Verifies the WebSocket environment against the requested environment.
7. Never logs or exposes the OTP.

This layer does not authorize trades, change live policy, submit orders, or bypass AURELIA capital controls.

Use either a Deriv OAuth 2.0 access token or PAT according to Deriv's current authentication flow. For PAT authentication, also supply `DERIV_APP_ID`. Store credentials only in an approved secret manager or deployment environment.

Recommended runtime variables:

- `DERIV_AUTH_TOKEN`: OAuth access token or PAT, supplied as a secret.
- `DERIV_APP_ID`: required for PAT authentication.
- `DERIV_EXPECTED_LOGINID`: exact account binding; required for real-money sessions.
- `DERIV_EXPECTED_CURRENCY`: `USD` for current Options accounts.
- `DERIV_ENVIRONMENT`: `real` or `demo`.

AURELIA remains `FINAL_EXECUTION_AUTHORIZATION=false` until its independent evidence and capital gates pass.

## Railway

The repository contains a deployment workflow using the Railway CLI and a project-scoped `RAILWAY_TOKEN`. Railway documents `RAILWAY_TOKEN` as the project-level CI/CD credential for `railway up`.

The current Railway project exists but has no service while the connected Railway account reports an expired trial. Deployment cannot be completed until the Railway account has an active plan and the project has an executable service entitlement.

Do not put a Railway token or Deriv credential in this repository or in chat.

The deployment workflow is deliberately inert when `RAILWAY_TOKEN` is absent and never changes AURELIA's live-execution flags.
