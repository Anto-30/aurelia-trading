# AURELIA Modern Deriv Options API Path

## Canonical transport

AURELIA's current Options integration uses Deriv's modern API contract:

- REST base: `https://api.derivws.com`
- Account inventory: `GET /trading/v1/options/accounts`
- Authenticated WebSocket bootstrap: `POST /trading/v1/options/accounts/{accountId}/otp`
- Authenticated real WebSocket: `wss://api.derivws.com/trading/v1/options/ws/real?otp=...`
- Authenticated demo WebSocket: `wss://api.derivws.com/trading/v1/options/ws/demo?otp=...`
- Public market-data WebSocket: `wss://api.derivws.com/trading/v1/options/ws/public`

Deriv documents the OTP as short-lived (120 seconds) and single-use. The OTP response supplies the ready-to-use WebSocket URL, so AURELIA must generate a fresh OTP and connect promptly. PAT authentication requires the `Deriv-App-ID` header for REST authentication.

## AURELIA implementation

The canonical code path is:

`runtime/adapters/session_manager.py`
→ `runtime/adapters/deriv_session.py`
→ `runtime/adapters/deriv_adapter.py`
→ `runtime/adapters/deriv_ws.py`

The runtime verification path is:

`AUTHORIZED CREDENTIAL`
→ account inventory
→ exact account binding
→ fresh OTP
→ authenticated Options WebSocket
→ identity/currency/environment verification
→ fresh balance snapshot
→ capital snapshot

The verification path does not authorize capital or submit an order.

## Legacy endpoint policy

Legacy `ws.derivws.com` / Binary WS v3 endpoints are not a production fallback. They may be referenced only in diagnostics/tests/documentation that explicitly identify them as legacy.

Executable production code must validate the modern host and Options WebSocket path before establishing an authenticated session.

## Security

Never commit or log:

- PATs
- OAuth access or refresh tokens
- OTP values
- authenticated WebSocket URLs containing OTPs
- passwords or private keys

Evidence should contain only redacted endpoints and non-secret verification metadata.

## Operational qualification

Successful Deriv authentication is necessary but not sufficient for live capital movement. AURELIA must still satisfy the existing strategy, calibration, economics, soak, risk, firewall, capital-plane, reconciliation, watchdog, idempotency, deployment, and release-lock requirements before any live order is authorized.
