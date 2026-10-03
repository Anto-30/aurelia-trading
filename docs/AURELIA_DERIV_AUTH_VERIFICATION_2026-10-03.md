# AURELIA Deriv authenticated-session verification

AURELIA's external Deriv prerequisite is now a first-class operational verification path.

The runner uses the existing session manager to:

1. Discover/select the exact bound account.
2. Request a fresh account-specific OTP.
3. Connect to the authenticated Options WebSocket.
4. Verify login ID, account type, environment, and currency.
5. Read a fresh broker balance snapshot.
6. Write a genuine evidence envelope when the external credentials are valid.

The verifier does not submit an order and does not grant capital authority. A successful verification still reports:

`FINAL_EXECUTION_AUTHORIZATION=false`

`LIVE_EXECUTION=BLOCKED`

Required GitHub Actions secrets for real-account verification:

- `DERIV_AUTH_TOKEN`
- `DERIV_EXPECTED_LOGINID`
- `DERIV_EXPECTED_CURRENCY` (normally `USD`)
- `DERIV_APP_ID` when the token is a PAT

OAuth access tokens do not require `DERIV_APP_ID`. PAT authentication does. Deriv's current API contract uses a short-lived, one-time account-specific OTP to establish the authenticated Options WebSocket session.

The exact balance amount is retained only in the generated evidence object; the verifier does not print the amount to CI logs.
