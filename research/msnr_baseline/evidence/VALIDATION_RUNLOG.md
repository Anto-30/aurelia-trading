# MSNR validation run log — 2026-10-22 UTC

## Repository and safety inspection

- Canonical repository: `Anto-30/aurelia-trading`.
- Exact main commit confirmed by GitHub: `d04564aca0648201feff0326fe9af0fbcee92e94`.
- Canonical `config/LIVE_LOCK.yaml` blob SHA: `b2cddd1efb0f25f35a6a08354290f805812bf34c`.
- Lock values read remotely: `live_trading_enabled: false`, `LIVE_EXECUTION: BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION: false`, `capital_plane_mode: VERIFY_ONLY`.
- Local bundle is an exported working bundle, not a Git checkout. The exact repository commit above came from GitHub, not from local `git rev-parse HEAD`.
- No Remote Desktop Commander device was connected.

## API and model checks

- Public WebSocket only: `wss://api.derivws.com/trading/v1/options/ws/public`.
- No authentication, account token, OTP, account balance, proposal/buy/sell or order methods.
- Uses `underlying_symbol`; candles require `open`, `high`, `low`, `close`, `epoch`; no `loginid` is used.
- Current `active_symbols` comparison maps legacy `pip` to `pip_size` and presents it as a price-unit increment. A similarly named `pip_size` in tick/history responses may represent display precision; the code does not conflate those shapes.
- Official schema references: https://developers.deriv.com/comparison/active-symbols/ and https://developers.deriv.com/comparison/ticks-history/.

## Local verification

```text
python -m compileall -q scripts tests
pytest -q
```

Result: 11 tests passed in the isolated MSNR package; 21 tests passed in the whole exported validation bundle. CLI help smoke checks passed for `fetch_history.py`, `verify_history.py`, and `run_msnr_simulator.py`. Tests are only structural/control-flow evidence; fixtures are not market data.

## Latest public API fetch attempt

Command:

```text
python scripts/fetch_history.py --start-date 2022-10-21 --end-date 2024-10-21 --output-dir evidence/fetch_attempt_20261022_finish --timeout 4 --retries 0 --retry-delay 0 --chunk-days 3
```

Observed result: exit status 2, `FAILED_CLOSED`; the host failed DNS resolution before any `active_symbols` response. Exact record: `evidence/fetch_attempt_20261022_finish/fetch_run.failure.json`. It records `market_data_received: false`, `account_token_used: false`, `otp_used: false`, and `live_orders_submitted: false`.

No candles, data CSV/manifest, independent verifier report or simulator execution resulted. Full-range row targets are 1,054,080 1m bars and 70,272 15m bars; these are calculated expected counts, not observed rows.

## Empirical/release disposition

- Profit factor, net expectancy and drawdown: NOT COMPUTED.
- Trade ledger/Holy Trinity run output: NOT PRODUCED.
- Kill rule: NOT EVALUATED; DNS failure is not evidence of strategy failure.
- 3,600-second soak, authenticated verify-only lifecycle evidence and independent review: NOT COMPLETED.
- Strategy qualification and live execution: BLOCKED / VERIFY_ONLY.
