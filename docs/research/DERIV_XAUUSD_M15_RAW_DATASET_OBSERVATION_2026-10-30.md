# Deriv XAUUSD M15 Raw Dataset Observation — 2026-10-30

**Status:** Retrieved raw source sample; not yet an approved research dataset and not a strategy backtest. Latest preserved snapshot: 2026-10-30 17:16:38 UTC; GitHub Actions run #59 (36 unit tests passed).

## Acquisition

- Provider: Deriv public market-data WebSocket; no account authentication.
- Endpoint: `wss://api.derivws.com/trading/v1/options/ws/public`
- Exact symbol: `frxXAUUSD`; provider schedule names it **Gold/USD**, Commodities → Metals.
- Timeframe: 900 seconds (M15).
- Requested: 5,000 candles.
- Returned: 5,000 candles, in 9 pages.
- First bar start: 2026-08-14 07:30:00 UTC.
- Last bar start: 2026-10-30 17:15:00 UTC.
- Closed bars at the server-time check: 4,999.
- Current/final bar at retrieval: not yet closed; excluded from completed-bar analysis.
- Normalized CSV SHA-256: `6f2813df62238a237ce8bef6b834b9a02cdf64070b3900e899d3b6700c2f6cfd`.
- Combined raw page-hash SHA-256: `91b24c40ee5580bd5162e9b7e73277c6760064060875096ef7644aa9273f9b64`.
- Trading-times calendar sidecar SHA-256: `214539102a99e06c249538f55d7abe36fc350cffb7cac6e128b92752e488ed9d`.

## Structural data checks

| Check | Result |
|---|---:|
| Rows | 5,000 |
| Duplicate timestamps | 0 |
| Strictly increasing timestamps | PASS |
| Finite numeric OHLC | PASS |
| Positive OHLC | PASS |
| OHLC high/low relationship | PASS |
| Closed bars | 4,999 |
| Unclosed bars | 1 |
| UTC 15-minute grid-aligned bar starts | 4,995 |
| Off-grid bar starts | 5 |
| Consecutive intervals not equal to 900 seconds | 65 |
| Intervals shorter than 900 seconds | 10 |

Observed non-900-second intervals:

- 42 intervals of 4,500 seconds (75 minutes), including repeated 20:45 → 22:00 UTC timestamp gaps.
- 11 intervals of 184,500 seconds (51 hours 15 minutes), matching the observed Friday 20:45 → Monday 00:00 pattern.
- 1 interval of 19,800 seconds (5 hours 30 minutes), from 2026-09-07 18:30 UTC to 2026-09-08 00:00 UTC.
- 9 intervals shorter than 15 minutes: 97, 300, 301, 599, 600, 600, 600, 803 and 900? seconds.

Off-grid candle start timestamps:
- 2026-08-14 10:54:59 UTC
- 2026-08-18 20:40:00 UTC
- 2026-09-08 10:55:00 UTC
- 2026-09-29 10:55:00 UTC
- 2026-10-20 07:02:07 UTC

No records were sorted, deduplicated, dropped, forward-filled or altered. The 2,437 unadjusted missing 15-minute slots are a raw arithmetic count and **must not be described as 2,437 missing feed bars**: it includes time outside sessions/weekends and other irregular intervals.

## Trading-times evidence

Latest normalized CSV hash is bound to the raw-page hash and two-date schedule sidecar recorded above; the short-retention Actions artifact is available from [run #59](https://github.com/Anto-30/aurelia-trading/actions/runs/41097341310/artifacts/12996682885).

The public `trading_times` API was queried for 2026-08-14 and 2026-10-30. Both responses included a schedule entry with:
- `underlying_symbol = frxXAUUSD`
- `name = Gold/USD`
- `market = Commodities`, `submarket = Metals`
- `trading_days = Mon–Fri`
- `times.open = 00:00:00`
- `times.close = 20:55:00`
- An event stating Friday early close at 20:55
- A dated early close on 2026-09-07 at 18:30 in the 2026-08-14 response

The 5-hour-30-minute gap on 2026-09-07 from the final 18:30 candle start to the next 00:00 bar is consistent with that dated early-close event.

However, the ordinary data pattern resumes at 22:00 UTC after a 20:45 candle start, while the schedule's `times.open` field is `00:00:00`. The API documentation does not establish the timezone normalization needed to reconcile this `open` field with the observed UTC series. The two-date sample is also not a historical day-by-day holiday calendar. Therefore the session calendar is **not yet reconciled** and the data must retain the status `GAPS_REQUIRE_INSTRUMENT_SESSION_CALENDAR_REVIEW`.

## Research decision

**Permitted:** use this as a raw, hash-identified observation set for further data-quality and session-calendar investigation.

**Not permitted yet:** run the T4F strategy backtest, calculate strategy expectancy/PF, claim continuous M15 history, treat every timestamp as a completed 15-minute candle, or infer that all gaps are ordinary scheduled closures.

Before outcome measurement, implement a source-backed expected-session calendar, explicitly classify full bars vs partial/session-boundary bars, exclude only observations that fail the frozen data policy, preserve all exclusion counts, and create a new normalized dataset hash. Then freeze the T4F structural and execution rules independently of observed outcomes.

## Governance

This is a research dataset only. It grants no account access, capital authority, order submission permission, or live-release approval. AURELIA remains `LIVE_EXECUTION=BLOCKED`, `capital_plane_mode=VERIFY_ONLY`, and `FINAL_EXECUTION_AUTHORIZATION=false`.
