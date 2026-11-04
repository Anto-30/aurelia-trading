# Deriv OAuth Authorization Code + PKCE — AURELIA

## Provider contract

AURELIA uses the Deriv Authorization Code + PKCE flow with S256 only.

- Authorization endpoint: `https://auth.deriv.com/oauth2/auth`
- Token endpoint: `https://auth.deriv.com/oauth2/token`
- OAuth scope requested: `trade` only.
- Deriv documents `trade`, `account_manage`, `application_read`, and `payment`; it does not document a trading-account `read` scope.
- The Options account-list and OTP endpoints require `trade`. AURELIA's allowlist is therefore an application-level restriction, not a provider read-only permission.
- Deriv does not issue refresh tokens. The access-token expiry is derived from `expires_in`; expiry or an authorization failure requires a fresh user authorization.
- The authenticated Options OTP is single-use and short-lived. AURELIA must obtain a fresh OTP for a new authenticated WebSocket session.

## Flow boundaries

The OAuth helper attaches to the existing `DerivAdapter`; it does not replace or construct a WebSocket transport. The token exchange is an HTTPS request made by the server-side OAuth helper. Pending PKCE verifier data and the access token are stored through the existing Fernet-backed binding store in an encrypted sidecar using the same injected Fernet key and filesystem lock.

The state value is stored as a SHA-256 digest. The verifier is encrypted at rest. Callback state is bound to a high-entropy server-authenticated session binding and consumed durably before the token exchange. A failed exchange requires a new authorization; state cannot be replayed.

The session binding must originate from an authenticated server session, such as a host-only Secure, HttpOnly, SameSite=Lax cookie. It must not be accepted as an arbitrary value supplied by an unauthenticated browser. The web callback route, cookie issuance, origin/host validation, and deployment TLS configuration are deployment integration requirements and are not provided by the OAuth service class alone.

The access token is never returned in the authorization result. It is available only through a server-side method intended for an authenticated broker component. No token or provider error body is written to logs. Local deletion is not represented as provider-side revocation.

## Configuration and activation

`config/oauth_allowlist.yaml` ships with an empty `redirect_uris` list. This is intentional. OAuth cannot start until the deployed HTTPS callback is registered in the Deriv developer portal and the same exact URI is committed to the allowlist. The real Deriv application ID must be injected through `DERIV_OAUTH_APP_ID`; it must not be committed.

No default production hostname, redirect URI, application ID, client secret, API token, or provider credential is invented. The dedicated PKCE token exchange uses the documented code, client ID, redirect URI, grant type, and code verifier parameters. No client secret is added to the PKCE exchange by this implementation.

## Security and release semantics

OAuth consent does not authorize an order. The existing adapter allowlists, canonical executor capability, risk controls, kill switch, reconciliation, release gate, and `config/LIVE_LOCK.yaml` remain authoritative. External providers and agent workers receive no capital authority.

The integration has not been tested against a real Deriv app registration or authenticated account in this PR. Unit tests use injected token-exchange fixtures and encrypted local storage. A real authenticated demo lifecycle, independent human review, verified runtime identity/signing, durable production storage/KMS, and soak evidence remain separate release gates.

## Review checklist

- [ ] Deriv application registration matches the exact HTTPS callback and app ID.
- [ ] PKCE S256 and state/session binding are verified.
- [ ] Pending state is consumed once and cannot be replayed.
- [ ] OAuth state and access token are encrypted at rest.
- [ ] Only `trade` is requested and any additional granted scope is rejected.
- [ ] No refresh-token flow is implemented or assumed.
- [ ] Provider token and error payloads are not logged or returned to the browser.
- [ ] The adapter retains the existing WebSocket transport.
- [ ] OAuth does not modify LIVE_LOCK or grant executor authority.
- [ ] Authenticated demo lifecycle and broker reconciliation are independently evidenced.
- [ ] All strategy qualification and final release gates remain unsatisfied until their own evidence is complete.
