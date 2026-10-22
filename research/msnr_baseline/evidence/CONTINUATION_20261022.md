# MSNR continuation record — 2026-10-22 UTC

## Repository-intake result
Ten submitted repositories were triaged in docs/REPOSITORY_INTAKE.md. No external repository is approved for wholesale vendoring. FastAPI is the only core framework reference that aligns with the existing Python direction. The Benavlabs FastAPI boilerplate is reference-only; the Preact dashboard and Kokoro TTS options are deferred. FastEndpoints and Android/iPhone tether utilities do not fit the current architecture. GPL-3.0 template code and Pipedream source with repository license metadata NOASSERTION are not to be copied without licensing review.

## Added research utilities
- scripts/deriv_public_market_data.py provides a public-only client restricted to active_symbols, ticks_history and ticks. It rejects auth, account, and trade payloads and validates current history/candle response fields.
- scripts/performance_ledger.py accepts raw pre-cost trade CSVs and requires explicit cost assumptions. It reports post-cost expectancy, net profit factor, R multiples, win rate, transaction-cost components and trade-close drawdown. Inputs containing derived cost/PnL fields are rejected to prevent double charging.
- tests/test_public_client_and_performance_ledger.py tests these controls and formulas.

## Local verification
- Research directory: 17 tests passed.
- Whole exported bundle: 27 tests passed.
- Python compileall and CLI help checks passed.
- These are structural/unit tests, not an empirical trading result. Test fixtures are not market data.

## Latest history acquisition attempt
The public endpoint attempt failed before any API response because DNS could not resolve api.derivws.com. The adjacent fetch_run.failure.json states that market_data_received=false, account_token_used=false, otp_used=false and live_orders_submitted=false.

No verified R_100 candle CSVs, manifests, trade ledger, profit factor or expectancy were produced. Kill rule remains NOT EVALUATED. This failure does not mean that the strategy passed or failed.

## Safety disposition
Canonical config/LIVE_LOCK.yaml remains untouched on main. LIVE_EXECUTION=BLOCKED, FINAL_EXECUTION_AUTHORIZATION=false, and capital_plane_mode=VERIFY_ONLY. No PAT, OTP, authenticated broker session or live-order operation was used. PR #188 must remain draft until source review, empirical validation on genuine data, contract/cost qualification, non-production soak and independent review are complete.
