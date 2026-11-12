# Deriv MT5 historical tick import

## Why this path exists

An earlier public Options WebSocket probe returned current R_100 timestamps for explicit 2022 historical requests, even when the echoed request contained the old time boundary. This is a recorded prior observation, not a fresh verification. Re-run `scripts/probe_deriv_historical_semantics.py` against the requested window before relying on any returned data. The historical dataset gate remains blocked until the returned tick and candle timestamps verify the requested window. The legacy WebSocket smoke previously failed its handshake with HTTP 520; that failure is also historical and should be rechecked before treating the legacy endpoint as available.

Deriv documents exporting historical ticks from the MT5 **PC application**: open Market Watch, select the symbol, open Symbols, use the Tick tab, select the market/timeframe, then choose **Export ticks**. See the [Deriv community instructions](https://community.deriv.com/t/deriv-mt5-historical-data/29430).

## Import requirements

Do not infer any of the following:

- Exact MT5 Market Watch symbol. Supply the symbol exactly as displayed.
- Timezone used by the exported timestamps. Supply the actual MT5 server timezone; do not assume UTC, EET, or EEST.
- Equivalence between MT5 price data and the Deriv Options/Multipliers feed. The importer explicitly leaves this unverified.
- Equivalence between `R_100` and `1HZ100V`. They are different instrument identifiers and must never be substituted without a separate strategy revalidation.

The importer rejects naive timestamps without a timezone, ambiguous/nonexistent DST timestamps, invalid bid/ask values, out-of-order rows, and incomplete M1/M15 coverage. It never interpolates missing bars.

## Command

After exporting the target instrument's tick history from MT5, run:

```bash
python -m research.labs.import_deriv_mt5_ticks \
  --input /path/to/your/mt5_ticks_export.csv \
  --output-dir artifacts/r100-mt5-import \
  --source-symbol "<exact Market Watch symbol>" \
  --canonical-symbol R_100 \
  --source-timezone "<actual IANA server timezone>" \
  --start-epoch 1666310400 \
  --end-epoch 1729468800 \
  --confirm-symbol-mapping
```

The window is `[2022-10-21T00:00:00Z, 2024-10-21T00:00:00Z)`. The symbol confirmation flag is an explicit operator assertion, not an automatic broker verification.

## Outputs

- `R100_M1.csv`
- `R100_M15.csv`
- `manifest.json` with source SHA-256, normalized output hashes, actual coverage, gaps, ordering checks, source timezone and mapping assertion.

A `RESEARCH_IMPORT_READY` result means only that the exported MT5 data passed import integrity and operator mapping checks. It does **not** mean that the feed is equivalent to Deriv Options/Multipliers, that the strategy has a positive out-of-sample edge, or that any execution path is authorized. The manifest permanently records:

- `feed_equivalence_to_deriv_options_verified=false`
- `strategy_validation_eligible=false`
- `order_submission_permitted=false`
- `capital_authority_granted=false`

The next research gate must compare overlapping live timestamps from MT5 and the Options feed, reconcile candle boundaries and price precision, then run the full cost-aware WFO on the exact imported data.
