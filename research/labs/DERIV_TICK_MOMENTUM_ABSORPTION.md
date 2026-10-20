# Deriv Tick-Momentum Absorption Lab

## Purpose and safety boundary

This is a research-only implementation for AURELIA's research area. It does not connect to a broker, submit orders, manage live positions, grant capital authority, or change config/LIVE_LOCK.yaml. The code tests whether a price-behaviour proxy has forward statistical value; it does not validate the video's institutional-absorption thesis on synthetic indices.

## Run

Install NumPy and pandas, then run:

    python -m unittest research.labs.tests.test_deriv_tick_momentum_absorption -v
    python -m research.labs.deriv_tick_momentum_absorption --csv R75_6months_1min.csv --out wf_deriv_absorption --contract-type all --tick-size 0.01

The input CSV must contain timestamp, open, high, low, close and volume. Timestamps are normalized to UTC. Invalid OHLCV records and duplicate timestamps are counted and dropped. Time gaps are reported and never filled or forward-imputed.

## Outputs

Each contract proxy receives its own directory with folds.csv, oos_trades.csv and summary.json. comparison.json summarises all three runs. The 48-combination signal parameter grid is optimized separately per contract model. Multiplier, payout, duration and friction assumptions are held fixed during each signal optimization to reduce parameter-selection bias.

## Interpretation and remaining work

- For Deriv synthetic indices, close-direction multiplied by bar volume is a tick-momentum proxy, not true bid/ask aggressor delta.
- OHLCV data does not contain true volume-at-price. The volume profile distributes each bar's volume uniformly over the price bins its low-high range covers.
- Rise/Fall is a fixed-expiry binary payoff screen; structural stop-loss/take-profit logic is not applied. Equal entry/expiry prices count as losses.
- CFD and Multiplier cash P&L calculations are approximations. Actual quote commissions, payout, contract mechanics, entry/exit prices and slippage must replace placeholders before interpreting performance economically.
- Run with actual historical input, verify coverage and gaps, inspect every OOS fold, then conduct a pre-committed demo/paper forward test. An OOS gate PASS means paper validation only.
- Never wire this research module directly to the capital plane. No research result can authorize execution or alter release controls.
