# AURELIA ML Research Architecture — RLSTM-IBTI v0.1

RLSTM-IBTI is a research-plane model combining the ResNLS ResNet/LSTM concept with leakage-safe intra-bar timing features inspired by the VWAP-timing research.

It is not a second trading engine and has no capital, broker, LIVE_LOCK, or execution authority.

ResNLS reports a ResNet feature extractor followed by LSTM and a five-day input choice on the studied equity-index data. Those results are not assumed to transfer to Deriv synthetic indices. The timing research motivates completed-bar high/low temporal-position features; conventional VWAP semantics must not be assumed without appropriate volume data.

Feature families: OHLC, returns, candle geometry, completed-bar timing, deterministic Aurelia rule state, forecast residuals, regime state, and non-leaking execution/economic context.

Every feature must carry an availability timestamp. A feature becoming available after the decision timestamp is invalid.

Architecture: feature tensor -> residual CNN blocks -> LSTM -> multi-task heads. Heads: calibrated win probability, expected return, expected MAE, expected MFE.

Research protocol: freeze baseline; build leakage-safe Deriv dataset; run ablations; test lookbacks 16/32/64/128/256; chronological walk-forward; calibrate on validation only; evaluate net contract economics; segment by instrument/timeframe/regime; shadow test; promote only after OOS, calibration, economics, robustness, provenance, and shadow evidence.

Model registry states may include RESEARCH, CHALLENGER, SHADOW, CHAMPION, QUARANTINED, and RETIRED. Promotion does not change capital authorization.

Initial model: RLSTM-IBTI-v0.1. Initial architecture defaults: kernel 3, 64 filters, LSTM hidden 32, dropout 0.20, default lookback 32. These are research defaults, not production claims.
