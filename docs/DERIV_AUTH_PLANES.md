# Deriv authentication-plane policy

**Status: enforced fail-closed; account evidence unavailable.**

## Public research plane

Layer 9 uses only the unauthenticated public market-data WebSocket:

`wss://api.derivws.com/trading/v1/options/ws/public`

No bearer token, PAT, OAuth token, app ID, cookie, or account metadata is sent. This endpoint provides public market data and contract metadata; account-scoped actions such as balances are unavailable on it. Public research must reject account credentials in its process environment and must not request proposals or submit orders.

## Account-evidence plane

AURELIA's current Options account-evidence flow is blocked. Deriv's current official Options API scope table assigns OAuth `trade` scope to:

- `GET /trading/v1/options/accounts` (account discovery)
- `POST /trading/v1/options/accounts/{accountId}/otp` (authenticated WebSocket bootstrap)

Deriv documents `application_read` as read-only access to registered applications, not account balances. No read-only account scope for the required account endpoints is documented in the current scope table.

Sources:
- https://developers.deriv.com/docs/options/
- https://developers.deriv.com/docs/options/websocket/
- https://developers.deriv.me/docs/intro/oauth/

Consequently, the following are not acceptable substitutes for a read-only account scope:
- a trade-scoped PAT or OAuth token;
- a token used only for a GET request;
- a manual workflow dispatch from `main`;
- a job labelled `VERIFY_ONLY` or `NO_ORDERS`.

The verifier `scripts/verify_deriv_session.py` therefore fails closed before reading environment values, obtaining credentials, constructing an authenticated adapter, calling account endpoints, requesting an OTP, opening an authenticated account WebSocket, or reading a balance. The protected account-evidence workflow emits a fixed blocked reason and receives no production secrets.

## Secret presence and deployment

The production secret-presence workflow may evaluate whether GitHub secrets are present, but it passes only boolean results to the reporting process. It must never copy token, SSH key, known-host, or signing-key values into the Python process environment. Presence does not establish validity, least privilege, or deployment readiness.

The separate self-hosted deployment workflow may contain credentials only in explicitly LIVE-gated steps, with its source-revision and `LIVE_LOCK` checks occurring before any credential-bearing step. This is not permission to change the lock or deploy. The canonical policy remains:

- `live_trading_enabled: false`
- `FINAL_EXECUTION_AUTHORIZATION: false`
- `LIVE_EXECUTION: BLOCKED`
- `capital_plane_mode: VERIFY_ONLY`
- `research_capital_authority: false`

## Conditions to reopen account evidence

Reconsider account verification only after:
1. Deriv officially documents a genuinely read-only scope for the exact account endpoints required.
2. The exact effective permission can be verified without requesting broader scopes.
3. A separate account-evidence component is designed and independently reviewed.
4. Automated tests prove PAT, generic tokens, refresh tokens, and trade-scoped OAuth tokens cannot enter the account-evidence plane.
5. An independent security reviewer approves the design and a protected-main run proves only the approved read-only scope is used.

Until then, account balances, authenticated lifecycle evidence, account-scoped strategy qualification, and LIVE deployment remain blocked. Public market-data research may continue without authentication.
