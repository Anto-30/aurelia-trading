# AURELIA Current Operational State — 2026-10-03

This document records the currently verified state of the existing AURELIA implementation. It is not a live-capital authorization.

## Verified

- Canonical branch: `main`
- Repository: `Anto-30/aurelia-trading`
- GitHub remote read: verified
- GitHub remote write: verified
- Modern Deriv REST path: verified
- Modern Deriv OTP path: verified
- Authenticated Options WebSocket path: verified
- Real USD account binding: verified
- Fresh broker balance: 1.45 USD at the latest verification point
- Legacy `ws.derivws.com` / Binary WS v3 path: diagnostic-only; HTTP 520 is classified as a legacy endpoint failure
- Starting stake reference: 1.00 USD
- Stake ceiling: verified available balance
- No live orders submitted

## Not yet verified

- Railway production service/deployment/healthy worker
- Deriv authenticated session from Railway
- Deployment lineage from `main` to a running Railway worker
- Prospective multi-day OOS qualification
- Probability calibration and drift evidence
- Net execution economics
- 3600-second adversarial runtime soak
- Final live strategy eligibility

## Current release state

`FINAL_EXECUTION_AUTHORIZATION=false`

`LIVE_EXECUTION=BLOCKED`

`LIVE_ORDERS=0`

`config/LIVE_LOCK.yaml` remains the controlling release artifact.

## Railway blocker

The connected Railway control plane currently reports the existing project `AURELIA-Production-Worker` with no service or deployment. An attempted service creation/deployment was rejected by Railway because the account trial has expired and requires a plan selection. No substitute worker or duplicate project was created.

## Security

Credentials were not copied into GitHub. PATs, OAuth tokens, OTPs, authenticated WebSocket URLs, and other secrets must remain outside source control and logs.

## Operational rule

Authentication and a fresh balance are necessary but not sufficient for capital movement. AURELIA must continue to apply the existing Risk Warden, LivePolicy, Capital Plane Gate, Execution Firewall, Account Isolation, idempotency, reconciliation, watchdog, kill-switch, calibration, economics, soak, and release-lock requirements.
