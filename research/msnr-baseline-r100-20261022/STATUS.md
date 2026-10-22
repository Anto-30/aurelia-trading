# MSNR baseline R_100 — staging package

**Disposition: BLOCKED / VERIFY_ONLY.** This pull request stages research code only. It does not integrate anything into the AURELIA runtime and must not be merged as release authorization.

## Contents

- `source_bundle.tar.gz` is the exact source/config/test/evidence package. Extract it into `research/msnr_baseline/` to restore the package layout.
- The package contains a current-API public-WebSocket fetcher, a separate manifest/data verifier, a frozen deterministic price-action MSNR simulator, tests, config, and local evidence.
- Local checks: outer bundle 20 tests passed; MSNR package 10 tests passed; compileall and CLI help checks passed.
- Package SHA-256: `05c371a6e4312003c0bc030b775ce7a37cbdd0625c2d2bf7e24bb29cc7251a32`.

## Unresolved empirical gate

The fetch attempt failed before receiving a response because DNS could not resolve the public host (`gaierror: [Errno -3] Temporary failure in name resolution`). No historical candles, verified CSV/manifest, trade ledger, profit factor, or net expectancy exist. The kill rule has not been evaluated. Do not use tests/fixtures as market data or claim strategy performance.

## Frozen model and constraints

- 1m R_100 OHLC; three-day chunks; 1.5-second pacing; requested interval 2022-10-21 through 2024-10-21.
- Price-action sweep/reclaim with an ATR(14)-based stop/target and 200-period MA/slope regime gate; no HMM/LSTM, volume profile, order-flow, or retail oscillators.
- Vectorized causal features; signal at bar `i-1` is executed at open `i`; no price/indicator forward-fill.
- 90-day simulation segments, Numba stateful loop, append-only JSONL ledger and cleanup between segments.
- Cost assumptions remain assumptions. The multiplier 1.0 in the code is normalized research PnL, not a verified Deriv contract multiplier. This implementation remains NOT_QUALIFIED and is not evidence a supported linear instrument is available.

## Safety invariants

The canonical `config/LIVE_LOCK.yaml` was not changed. Its observed blob SHA-256: `b2cddd1efb0f25f35a6a08354290f805812bf34c`. Its state is `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`. No account token, OTP or live order was used.

Base commit: `d04564aca0648201feff0326fe9af0fbcee92e94`.

**Review requirement:** Once DNS is restored, fetch authentic history; verify coverage and hashes; independently confirm valid linear contract economics and costs; execute the frozen baseline once; evaluate the kill rule; add independent review. Keep this PR draft until the research code is unpacked, reviewed, and tested in the normal checkout.
