# ATOS v2.0 research validation

## Safety boundary
Research only. This package has no order-submission method and must not be wired directly to Layer 6 or the execution adapter. The canonical `config/LIVE_LOCK.yaml` is intentionally unchanged. `config/STAGING_PAPER.yaml` is a separate paper-mode profile and cannot override the canonical lock.

## Data
Deriv WebSocket API endpoint pattern: `wss://ws.derivws.com/websockets/v3?app_id=YOUR_APP_ID`; history requests use `ticks_history` with `style=candles` and `granularity`. See https://developers.deriv.com/docs/data/ticks-history/. API App ID is configuration, not a secret. Keep access tokens out of source and logs. Deriv synthetic-index candles do not provide exchange-traded volume; the adapter preserves volume as missing rather than fabricating it. Fetch in bounded windows and persist the raw responses with timestamps, request metadata, symbol, granularity, and content hashes. Current adapter requests one bounded response; production 12–24 month backfills must paginate/chunk by time and verify expected bar counts, UTC boundaries, duplicates, and gaps. It fails on detected gaps instead of filling them silently.

## Validation protocol
1. Sort and deduplicate source data, preserve missingness, and verify symbol availability/contract semantics.
2. Reserve the newest three calendar months by timestamp before any fitting or feature/parameter selection. Store its boundaries and hash in an immutable manifest.
3. Within older development data, run rolling WFA. Train all transforms and the HMM only on each training window. Predict subsequent held-out observations causally.
4. Replay each of the four models on identical market data and fold boundaries. Include spread, payout, commission (if contractually applicable), slippage, and latency assumptions sourced from observed contract quotes/fills; fail closed if costs are unavailable. Do not infer a universal synthetic-index commission or use invented volume.
5. Report net expectancy in R, profit factor, maximum drawdown, sample size, fold variance, confidence intervals, and fold-by-fold results. Account for multiple model/parameter trials and overlapping trades. Degradation above a preregistered 15–20% threshold triggers review/fallback; it is not proof of overfit.
6. Evaluate the sealed three-month OOS exactly once after choices are frozen. A failed/ambiguous OOS or cost source means no promotion.
7. Run paper mode and telemetry before any release review. Latency >200 ms is an alert threshold, not a guarantee of acceptable fills.

## Important limitations
- HMM states are unlabeled; regime names are heuristic mappings and can change between fits.
- The HMM uses Gaussian emissions and an approximate mapping; Alpha–Beta filtering should be compared against the standard HMM, MA control, and unfiltered MSNR.
- The four-model script consumes an audited trade ledger. It does not generate authentic MSNR trades from candles or invent model outputs. Strategy-specific trade generation and Deriv contract payoff/cost adapters remain required.
- ATR sizing requires the actual contract's monetary value per price unit and stop semantics. For fixed-payout contracts without a conventional stop, use stake/payout loss bounds rather than treating ATR sizing as a stop-loss guarantee.
- No live trading, real orders, or capital authorization is implemented.
