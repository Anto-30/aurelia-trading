# MSNR baseline R_100 — withdrawn staging branch

The earlier draft staging pull request was closed before review because the uploaded archive did not pass a byte-for-byte Git blob SHA-1 integrity comparison against the local source archive. **Do not use that archive.** The archive has been removed from the branch tree. No changes were merged to main.

The verified local source package is available as a separate conversation artifact. Its SHA-256 is recorded in the validation report delivered with it.

## Disposition

- Research status: BLOCKED / VERIFY_ONLY.
- Current Deriv public-WebSocket fetch: failed before receiving metadata because of DNS resolution failure.
- No verified historical candles, trade ledger, empirical profit factor, or net expectancy were produced. The kill rule remains unevaluated.
- Canonical `config/LIVE_LOCK.yaml` remains unchanged on main: `LIVE_EXECUTION=BLOCKED`, `FINAL_EXECUTION_AUTHORIZATION=false`, `capital_plane_mode=VERIFY_ONLY`.
- No credentials, OTPs, authenticated broker session, or live orders were used.

This branch is retained for traceability only. Do not merge it.