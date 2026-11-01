# ICT Silver Bullet â€” Research Status

**Status: research prototype only; not qualified; not integrated into capital execution.**

## Frozen hypothesis

- New York local windows: London 03:00â€“04:00, NY AM 10:00â€“11:00, NY PM 14:00â€“15:00, using `America/New_York` timezone rules.
- Sequential setup: confirmed liquidity sweep, opposite-direction market-structure shift/displacement, then a three-candle fair-value gap.
- Entry: FVG midpoint; stop: displacement-origin swing plus one provisional price-increment buffer; target: fixed 2R.
- Risk controls: 1% research risk per trade, 2% daily drawdown halt, and halt after four consecutive losses in a window.
- The baseline is frozen. Do not tune windows or thresholds against the OOS period.

## Implementation and tests

- `silver_bullet.py` implements research-only candle validation, New York session handling, causal confirmed pivots, sweep â†’ MSS â†’ FVG detection, and a deterministic OHLC backtest.
- `test_silver_bullet.py` contains 16 focused tests.
- `run_silver_bullet_research.py` fetches public Deriv candles, validates full timestamp coverage, writes data/trade/result artifacts, and hashes the data and configuration.
- Python compilation passed.
- Focused tests: **16 passed**.
- Full repository suite: **490 passed, 70 subtests passed**.

## Data and evaluation evidence

| Check | Result | Interpretation |
|---|---|---|
| R_75 M5, 2026-07-01 through 2026-10-31 | 35,424 candles; coverage PASS | Dataset was complete for the ¶»§q«^