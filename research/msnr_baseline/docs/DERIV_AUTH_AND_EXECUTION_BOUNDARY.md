# Deriv API integration boundary and review of supplied execution sample

**Disposition: RESEARCH-ONLY. Do not integrate the supplied authenticated execution sample into ATOS v2.0 or this branch.**

This review covers the pasted JavaScript/Python examples that request a PAT, fetch an authenticated OTP URL, subscribe to account balance, request proposals, and automatically submit buy when a proposal arrives. Those are order-capable flows, not public market-data or empirical-validation tools. This branch intentionally supports only the public Options WebSocket endpoint and has no credential, OTP, account, proposal, buy, sell, or cancellation path.

## Concrete defects in the supplied sample

1. **It can submit an order without a risk-engine decision.** The proposal handler immediately sends buy; a comment saying “trigger risk evaluation here” does not implement a gate. There is no deterministic pre-trade authorization object, stake affordability check, payout/cost EV gate, or kill-switch check.
2. **It silently converts a missing price into zero.** parseFloat(ask_price || 0) turns a missing optional field into a syntactically non-negative price. The fact that an API field is optional does not mean the application may invent a value. Reject the proposal unless the required fields for the chosen contract are present, finite, and pass a separately reviewed policy.
3. **It does not correlate all replies robustly.** Fixed request IDs, no pending-request map, and no timeout per request can associate the wrong response with a caller or leave the caller waiting indefinitely.
4. **Reconnect and shutdown handling are incomplete.** The sample can loop indefinitely on persistent auth/configuration errors, does not bound retry attempts, and does not consistently close the socket/session on cancellation. A 120-second OTP claim must be verified against current official documentation; never infer validity from an example comment.
5. **It assumes schema details without proving them.** Response msg_type, account-specific balance shape, proposal fields, contract-type compatibility, and symbol names must be validated against the current API reference and contract metadata. Never perform global symbol-to-underlying_symbol replacements on ticks_history: the request operation itself remains named ticks_history and its value is the short symbol.
6. **Credentials are placeholders, not configuration.** Never paste a PAT or OTP into chat, source, logs, artifacts, or workflow output. Do not ask for a secret in this workflow. If a credential has been exposed, revoke/rotate it in Deriv's account controls.
7. **It is not an MSNR execution adapter.** The sample uses an example CALL contract and a fixed duration, not a verified linear CFD/multiplier instrument. Binary Options/Rise-Fall cannot be represented as linear PnL on 1-minute OHLC candles.

## Allowed path for this validation task

- Use only wss://api.derivws.com/trading/v1/options/ws/public for unauthenticated public history/market data.
- Accept only the public operations explicitly allowlisted by deriv_public_market_data.py; reject credentials, account identifiers, OTP, balance, proposal, buy, sell and other account/trading payload keys at every nesting level.
- Fetch authentic R_100 candles, validate every OHLC/epoch field, requested date bounds, continuity and SHA-256; fail closed if the API returns recent data instead of the requested historical interval.
- Freeze MSNR parameters before evaluating performance. Use performance_ledger.py only on genuine raw trade records and explicitly declared assumptions; do not call the ledger output instrument qualification.
- Keep config/LIVE_LOCK.yaml untouched and LIVE_EXECUTION=BLOCKED, FINAL_EXECUTION_AUTHORIZATION=false, VERIFY_ONLY.
- Any future authenticated adapter requires a separate, explicitly approved scope, isolated credentials, a deterministic risk-engine authorization gate, no automatic proposal-to-buy transition, a mock/demo-only test plan, independent review, and the complete release gates. This document does not authorize that work.

## Cost ledger interpretation

The ledger requires explicit commission, spread, pip-size, slippage, multiplier and initial-equity arguments. Spread is explicitly named round-trip in the CLI to prevent ambiguity. The 5-bps slippage input is applied to each fill's own reference price. These are assumptions unless independently reconciled to a specific contract's actual economics and execution records. A multiplier of 1.0 is only a normalized research proxy. Commission, spread, slippage, and initial risk must use consistent units; do not report proxy results as broker-currency results.

## Current empirical status

The current PR's public-history probes have received recent candles but did not retrieve the requested 2022 and 2024 historical anchors. The pipeline must remain blocked until both bounds are honored and the full 24-month series is independently verified. No performance conclusion or kill-rule result follows from a data-retrieval failure.
