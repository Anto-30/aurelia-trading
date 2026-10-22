# MSNR baseline validation status — 2026-10-22

## Disposition
BLOCKED / VERIFY_ONLY. No empirical strategy result exists. The public history fetch was attempted against `wss://api.derivws.com/trading/v1/options/ws/public`, but this runtime failed DNS resolution (`Temporary failure in name resolution`). No substitute or synthetic data was generated.

## Implemented in this research-only branch
- New public WebSocket history fetcher for R_100 1m/15m candles, 3-day chunks, 1.5-second pacing, strict candle fields, CSV manifests and SHA-256.
- Strict CSV verifier for OHLC integrity, sorting, duplicates, hash mismatch and timestamp gaps >120 seconds.
- Frozen price-action MSNR baseline: 20-bar sweep/reclaim, MA200 regime gate, ATR(14), 1.5 ATR stop, 2 ATR target, prior-bar signal / next-bar open entry, no forward fill.
- Three-month data windows, chunked CSV reading, explicit `del` and `gc.collect()`, append-only JSONL ledger, seed 42 and required data/commit/seed hashes.
- Fail-closed instrument specification template; simulator refuses to run with unknown pip size, multiplier, equity or unverified contract economics.
- Automated guard tests.

## Not completed
- 24 months of genuine R_100 candles, their hashes/manifests and verified gap-free data.
- Independent verification of linear-contract multiplier, pip/point mapping, spread and slippage. The requested 2-pip / 5-bps costs cannot be converted to price units safely without that mapping.
- Empirical ledger, net expectancy, profit factor, out-of-sample evaluation, 3,600-second operational soak, and independent review.
- Therefore the kill rule has NOT been evaluated and the exact kill message must not be asserted.

## Safety
No credentials or authenticated endpoints used. No orders placed. The canonical `config/LIVE_LOCK.yaml` was not changed. This branch must not be merged as a live release; require CI, independent review and evidence from actual verified data first.
