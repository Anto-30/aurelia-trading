# Deriv Authentication Plane Policy

## State

- Layer 9 research: public unauthenticated market-data transport.
- Layer 6 account evidence: disabled until Deriv documents and exposes a verifiable read-only permission for the account APIs AURELIA requires.
- `LIVE_EXECUTION` remains `BLOCKED`.
- `FINAL_EXECUTION_AUTHORIZATION` remains `false`.
- No account credential is injected into research CI or the public market-data collector.

## Layer 9 — public research

The research client connects to Deriv's current public market-data WebSocket:

```text
wss://api.derivws.com/trading/v1/options/ws/public
```

No app ID, Authorization header, bearer token, PAT, cookie, or OAuth token is sent. It rejects a process environment containing any account credential variable, and rechecks that boundary before each request.

Allowed request families are limited to public market data and non-executing proposal quotes: active symbols, contract metadata, proposals, ticks, and tick history. The request validator also enforces an action-specific field allowlist. It rejects account authorization, buy/sell, and all unrecognized request fields.

`scripts/verify_deriv_public_transport.py` performs a live R_100 M1 historical-candle probe and writes hashed, non-secret evidence. A successful CI step is required before describing the endpoint as verified; the static prerequisite report alone only means the public plane is configured.

## Layer 6 — account evidence

The account guard requires `ACCOUNT_DERIV_AUTH_MODE=oauth` and never falls back to `DERIV_PAT` or `DERIV_AUTH_TOKEN`. If both OAuth and PAT values are present and equal, the guard raises `OAUTH_TOKEN_EQUALS_PAT`. Any PAT presence, generic token fallback, or unsupported refresh-token input is rejected.

Even a distinct OAuth access token is not sufficient. Current Deriv documentation does not expose a `read` scope for the required account endpoints; the account-list and OTP operations require the `trade` scope. A token with that permission cannot satisfy AURELIA's read-only account-evidence requirement. Therefore the account guard does not issue a client, and the session, broker-evidence, and transaction-lifecycle verifiers fail closed before any account request.

The GitHub Actions workflows do not map account tokens into the public research or assurance jobs. The GitHub secret provisioner, host read-only credential provisioner, and LIVE runtime credential provisioner are disabled. Existing secrets are not read, overwritten, or deleted by this change.

## Reopening account evidence

The account plane can be reconsidered only when all of the following are documented and tested:

1. Deriv supports a genuinely read-only scope for the exact account endpoints required.
2. The OAuth authorization response or a broker-supported introspection operation proves that scope, and binds the expected login ID and account environment.
3. CI maps the OAuth credential only to the isolated account-evidence job; no generic-token or PAT alias is present.
4. Integration tests prove that a PAT copied into the OAuth variable is rejected, and a genuine OAuth session is read-only.
5. Independent security review approves the change.

Until those conditions are met, authenticated account verification and LIVE deployment remain blocked.
