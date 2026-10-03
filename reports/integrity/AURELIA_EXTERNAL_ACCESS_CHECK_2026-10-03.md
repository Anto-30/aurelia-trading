# AURELIA External Access Verification — 2026-10-03

This is a timestamped, non-secret verification record for the current engineering integration.

## GitHub

- Repository: `Anto-30/aurelia-trading`
- Default branch: `main`
- Repository visibility: public
- Current observed `main` tip at verification: `69eccce8daf0c37c4a32818c225be7672201fb95`
- Connected integration repository permission: admin/maintain/pull/push/triage
- `main` is not protected by required status checks at this verification point.
- Direct GitHub read access: PASS
- Direct GitHub write capability: PASS from the current integration
- The earlier 403 reported by another runtime is therefore treated as an integration-session/credential-scope discrepancy, not as a repository-level inability to write.
- Do not make the repository public or relax repository security to solve another integration's permission problem.

## Railway

- Existing project: `AURELIA-Production-Worker`
- Project ID: `da9da5a1-acd2-4af2-9fec-bf46e4d4252b`
- Production environment ID: `bb95dc97-ad27-4b3a-8fa0-cf52df555a38`
- Services observed: none
- Deployments observed: none
- Worker observed: none
- Direct deployment attempt with the connected Railway control plane was rejected because the Railway trial has expired and a plan selection is required.
- No duplicate project or substitute trading worker was created.

## Deriv

The repository implementation now points the canonical AURELIA Options path at:

- REST: `https://api.derivws.com/trading/v1/options`
- OTP: `POST /trading/v1/options/accounts/{account_id}/otp`
- Real Options WebSocket: `wss://api.derivws.com/trading/v1/options/ws/real`
- Demo Options WebSocket: `wss://api.derivws.com/trading/v1/options/ws/demo`

Legacy `ws.derivws.com` / Binary WS v3 endpoints are diagnostic-only and are rejected by the executable endpoint validator.

The conversation's latest runtime report states that REST authentication, account binding, OTP WebSocket connection, and a fresh 1.45 USD balance were successfully verified. Those external runtime facts are not independently re-executed by this GitHub integration because Deriv secrets are not available to this tool and must never be committed.

## Capital controls

The current repository release control remains:

- `FINAL_EXECUTION_AUTHORIZATION=false`
- `LIVE_EXECUTION=BLOCKED`
- `live_trading_enabled=false`
- starting stake reference: 1.00 USD
- stake ceiling: authoritative verified available balance

No repository-side change in this verification grants capital authority.

## Remaining external dependency

The remaining infrastructure item that cannot be resolved by repository edits alone is Railway billing/plan authorization. A real Railway service must exist and run the current `main` source before Railway-side Deriv connectivity and the full runtime soak can be verified.
