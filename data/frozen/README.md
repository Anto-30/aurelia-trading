# Frozen R_100 research data

No R_100 raw 1-minute dataset was present in this repository when this workflow was built. Therefore no dataset manifest has been generated or committed; a fabricated manifest would invalidate the evidence lineage.

Place the authorized source CSV at `data/raw/r100_1m.csv`. It must contain `datetime,open,high,low,close`; optional extra columns (including any vendor-provided volume field) are not used as features. Specify whether timestamps represent the candle open or candle close; the tool normalizes to timezone-aware UTC candle-close labels.

From the repository root, run:

```sh
python -m research.labs.freeze_r100_dataset \
  --input data/raw/r100_1m.csv \
  --source "Deriv historical R_100 OHLC export; record request details" \
  --description "R_100 1-minute OHLC, exact UTC period and instrument metadata required" \
  --timestamp-role open
```

Use `--timestamp-role close` only when the CSV timestamps already mark candle closes. The tool rejects missing/invalid OHLC, timezone-naive timestamps, duplicate/out-of-order bars and one-minute gaps. It produces canonical 1m data, gap-free 15m bars aggregated from the same 1m source, hashes, row counts, ranges, and a combined manifest under `data/frozen/`. Outputs are immutable by default and are never overwritten. Keep the original source file unchanged.

A sealed hash verifies file identity, not correctness of the upstream source, strategy performance, or economic viability. The manifest therefore records `qualification_allowed: false`.

Walk-forward evaluation also requires verified instrument-specific costs. `config/costs.yaml` intentionally represents unknown spread and commission as `null`, while clearly marking the 1.5/3.0 point slippage values as unverified scenarios. Do not replace unknown values with zero or describe those assumptions as measured. The backtest must stop until source-backed costs have been recorded and verified.
