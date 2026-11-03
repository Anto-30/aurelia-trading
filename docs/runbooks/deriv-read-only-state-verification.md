# Deriv Read-Only State Verification

## Purpose and safety envelope

scripts/verify_deriv_read_only_state.py performs an authenticated, read-only
state snapshot using the repository's modern Deriv Options API session
manager and adapter. It does not request a proposal and does not call buy,
sell, cancel or any other order/contract mutation endpoint.

The script refuses to run unless the repository release configuration remains
locked in VERIFY_ONLY mode. It reads the local daily-risk and kill-switch
persistence files without modifying or resetting them.

## Authentication and API sequence

1. Read DERIV_AUTH_TOKEN (or the accepted PAT alias), expected account ID,
   currency, environment and application ID from the configured secret source.
   Never print or include token material in logs.
2. Use DerivSessionManager.bootstrap to obtain a short-lived authenticated
   WebSocket URL from Deriv's Options OTP endpoint. For PAT mode, the
   application ID is bound in the OTP request.
3. Connect DerivAdapter to the returned modern Options WebSocket URL. Do not
   send a second legacy authorize request after using an authenticated OTP URL.
4. Read balance: 1 once to verify account identity, currency, balance and
   available balance.
5. Read portfolio: 1 to observe open positions.
6. Read statement: 1 with a bounded current-UTC-day window and limit no
   greater than 999. Reconstruct the UTC-day opening balance from the broker
   statement and check the transaction balance chain.
7. Read balance: 1 again. Reject the snapshot if balance, available balance,
   account or currency changed while the reads were being collected.
8. Read the configured persistent daily-risk and kill-switch JSON files.
   Check their schema, account/currency binding, UTC day and timestamps, and
   hash their raw bytes. Do not initialize, reset or overwrite either file.
9. Write a local, hash-linked evidence record with source/config/data hashes.
   Record orders_submitted=0 and capital_movement=false.

No proposal, buy, sell, transaction subscription or proposal_open_contract
request is necessary for this snapshot. The statement endpoint is the bounded
historical record read; the transaction endpoint is subscription-based
streaming and must not be mistaken for a one-shot history query.

## Run

Set the environment only in the authorized runtime/secret manager. Required
values are:

- DERIV_AUTH_TOKEN (or configured DERIV_PAT alias)
- DERIV_EXPECTED_LOGINID (or configured authorized account ID)
- DERIV_EXPECTED_CURRENCY=USD for the current runtime policy
- DERIV_ENVIRONMENT=real
- DERIV_APP_ID for PAT mode
- AURELIA_DAILY_RISK_PATH and AURELIA_KILL_SWITCH_STATE_PATH pointing to the
  actual persisted runtime state files.

Command:

    python scripts/verify_deriv_read_only_state.py

The default local output is artifacts/deriv_read_only_state.json. Do not commit
account identifiers or generated account snapshots into a public repository.
The evidence is a read-only observation, not release certification and not
permission to submit orders.

## Failure semantics

Missing credentials, wrong account/currency/environment, stale or unstable
balances, incomplete/truncated statement, broken statement balance chain,
open/unreadable persistence files, wrong account binding, invalid schema or
malformed timestamps all produce DERIV_READONLY_STATE=BLOCKED. Unknown state
is never treated as a clean state.
