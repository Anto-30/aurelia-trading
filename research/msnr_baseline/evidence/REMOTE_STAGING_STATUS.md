# MSNR baseline validation status — 2026-10-22

**BLOCKED / VERIFY_ONLY; no empirical strategy result.**

- Canonical base commit: `d04564aca0648201feff0326fe9af0fbcee92e94`.
- This branch adds isolated research-only source/config/tests; do not merge to authorize a release.
- Local validation: 11 tests passed in package; 21 passed across whole working bundle; compileall and all three CLI-help checks passed. These are structural tests only.
- The latest current-public-API probe failed before any response because DNS could not resolve `api.derivws.com`. Failure evidence is in `research/msnr_baseline/evidence/fetch_run.failure.json`. No authenticated access was used and no market data was received.
- Consequently no CSV/manifests, independent verification report, trade ledger, profit factor, net expectancy, drawdown or Holy Trinity run output exists. Kill rule is NOT EVALUATED.
- R_100 linear-contract availability and multiplier remain unverified. Multiplier 1.0 is only a normalized price-PnL proxy; assumed spread/slippage and excluded commission cannot substantiate deployability.
- The canonical `config/LIVE_LOCK.yaml` on main remains unmodified: `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`.
- No account token, OTP, authenticated broker session or live order was used.
