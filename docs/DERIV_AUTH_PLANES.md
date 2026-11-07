# Deriv Authentication Plane Policy

## State

- Layer 9 research uses the unauthenticated public market-data plane only.
- Layer 6 account evidence is unavailable and remains blocked.
- `ACCOUNT_DERIV_AUTH_MODE` is `none` in every research, assurance, and account-prerequisite workflow.
- `LIVE_EXECUTION` remains `BLOCKED`.
- `FINAL_EXECUTION_AUTHORIZATION` remains `false`.
- No Deriv account credential is mapped into a research, assurance, account-prerequisite, or VERIFY_ONLY worker.

## Layer 9 — public research

The research client connects only to Deriv's public market-data WebSocket:

`wss://api.derivws.com/trading/v1/options/ws/public`

It sends no app ID, Authorization header, bearer token, PAT, cookie, OAuth token, or account metadata. It rejects a process environment containing any name in the canonical account-credential denylist, checking key presence without reading values, and rechecks the boundary before each request.

Allowed actions are restricted to public market-data and contract-metadata reads. Contract proposal/quote requests are disabled by policy; the research client rejects the `proposal` action as well as account authorization, buy/sell, order submission, and unrecognized request fields. Historical quote observations may be analyzed offline, but the prospective collector makes no new proposal requests.

`scripts/verify_deriv_public_transport.py` verifies R_100 active-symbol availability, M1 candles, and ordered live ticks over the credential-free public endpoint. A successful exact-head CI run and its hashed artifact are required before describing public transport as verified.

## Layer 6 — account evidence

There is no supported authenticated account mode in AURELIA's VERIFY_ONLY/account-evidence workers. The only accepted configuration value is `ACCOUNT_DERIV_AUTH_MODE=none`. The prerequisite reporter defaults to `none` and reports any `oauth`, `pat`, or other non-`none` value as invalid. This setting does not read, validate, or consume any token.

The required account-list and authenticated OTP endpoints are documented as requiring Deriv `trade` scope. No genuinely read-only account scope for these endpoints is documented. A trade-scoped OAuth token or PAT is therefore not an acceptable substitute and must never be configured, activated, tested, or used by a VERIFY_ONLY/account-verification worker.

`DerivAuthenticationGate(plane="account").get_client()` fails before any account request with `DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE`. The session, account-evidence, and transaction-lifecycle verifiers remain blocked. The public research process rejects all account credential environment keys; the account-prerequisite reporter checks key membership only and never retrieves values.

The GitHub workflows do not map Deriv credentials into research, assurance, account-prerequisite, or VERIFY_ONLY jobs. Existing GitHub secrets are not read, overwritten, rotated, or deleted by this change.

## Reopening account evidence

Account evidence can be reconsidered only after all of the following are independently established:

1. Deriv documents and exposes a genuinely read-only scope for the exact required account endpoints; `trade` scope is explicitly excluded.
2. Official broker documentation or a broker-supported introspection operation proves the effective read-only scope and account binding.
3. A separately designed, credential-isolated account-evidence component is reviewed; the public research and VERIFY_ONLY workers remain credential-free.
4. Tests prove that PAT, generic-token, refresh-token, and trade-scope credentials cannot enter or be consumed by the account-evidence path.
5. Independent security review approves the design and its least-privilege boundary.

Until those conditions are met, account-data access, authenticated lifecycle verification, strategy release, and LIVE deployment remain blocked.
