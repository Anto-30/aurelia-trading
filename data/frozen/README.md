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

Walk-forward evaluation also requires a verified instrument-specific cost and contract-economics profile. `config/costs.yaml` intentionally represents spread, commission, contract type, bar-price basis, and USD-per-point mapping as unknown; the 1.5/3.0 point slippage values are unverified scenarios. Do not replace unknown values with zero or describe the scenario values as measured.

The current backtester is only for a verified linear price-point P&L model using midpoint OHLC bars. Before enabling the runner, the verified source must establish `pnl_model: LINEAR_INDEX_POINT_VALUE`, `bar_price_basis: MIDPOINT`, `contract_type`, `usd_per_point_per_unit`, current spread/slippage/commission values, and source timestamps. If the actual Deriv contract has binary/multiplier or another payoff model, this linear backtester is not suitable; a contract-specific P&L simulator is required instead. Unknown or unverified costs fail closed.
