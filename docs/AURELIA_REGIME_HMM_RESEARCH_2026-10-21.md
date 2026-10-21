# AURELIA Regime HMM Research Prototype — 2026-10-21

## Status and boundary

**Status: research prototype only.** This work does not qualify a strategy, change risk limits, authorize trades, connect to a Deriv account, or alter config/LIVE_LOCK.yaml. LIVE_EXECUTION remains BLOCKED, capital-plane mode remains VERIFY_ONLY, and FINAL_EXECUTION_AUTHORIZATION remains false.

The module now includes (1) a conventional Gaussian-HMM forward filter and (2) a paper-style alpha-beta belief recursion. The latter implements the equal-exit prediction and tempered-likelihood update from Sui et al. (arXiv:2504.01759). Its emission means/covariances are still estimated by a GaussianHMM EM fit, so this is a hybrid research implementation—not a complete replication of every training/experimental detail in the paper—and must be benchmarked against a full-transition HMM baseline.

## Corrections to the initial skeleton

- GaussianHMM.predict() returns a decoded state sequence; it is not the persistent online filter required here. Re-running it on the last 20 samples resets the sequence context. Both filter adapters in this module instead persist belief and update once per completed bar. The alpha-beta variant uses the paper-style scalar exit parameter `alpha` and evidence step-size `beta`, not the model transition matrix.
- State IDs are arbitrary and permutation-invariant. Mapping is recalculated from each fit's parameters, never by assuming state 0/1/2 have fixed meanings.
- The original covars_[:, 1, 1] test examines the covariance of the volatility feature, not the mean volatility level. This prototype maps the state with the highest training-standardized mean rolling volatility only when it clears an explicit threshold. Labels are heuristics and require fold-by-fold diagnostics.
- Scaling is fitted on each training window only. Test observations are transformed with those frozen statistics. Fitting or scaling on train+test data leaks future distribution information.
- A low-confidence or high-entropy posterior returns UNDEFINED; malformed data and numerical failures raise errors. This is not capital authorization and must never be converted to a trade by default.
- Deriv candle data is OHLC plus epoch in the documented ticks_history candle response; do not assume OHLCV volume exists. Confirm symbols via active_symbols, page by time window, retain epoch timestamps, and audit gaps/duplicates before fitting.

## Minimal workflow

1. Retrieve historical candles for a confirmed symbol and granularity using Deriv's supported market-data WebSocket API. Store the raw response unchanged with retrieval time, requested interval, symbol, and payload hash. This prototype makes no API request itself.
2. Sort and de-duplicate by candle epoch. Reject malformed or missing OHLC bars; do not interpolate missing candles without a separately justified policy.
3. Generate [log_return, rolling_sample_volatility] after each completed candle. Preserve feature-to-candle timestamp alignment.
4. Build fixed, chronological train/test folds; for example, train on the prior 500 eligible observations and evaluate the next 50, rolling forward without overlapping test windows. Fit scaler and HMM inside each fold's training segment only.
5. For each held-out bar, call the causal filter once, in timestamp order, and record posterior, confidence, normalized entropy, label, and decision timestamp. Do not use smoothed/Viterbi historical labels as live features.
6. Replay unchanged strategy rules on the same entries/exits and compare filtered versus unfiltered results after the same verified payout, fees, slippage, and latency assumptions. Report net expectancy in R, profit factor, max drawdown, trade count, regime-cell sample size, and uncertainty intervals. Also report how many entries the filter blocks.
7. Keep the full, untouched prospective OOS set sealed. Do not change thresholds or models after inspecting that set; each changed model begins a new evaluation version and needs new prospective evidence.

## Research-only dependency

Install the optional fitting dependencies from the repository root:

    pip install -e '.[research-hmm]'

The posterior update, feature engineering, state mapping, and tests use the Python standard library; fitting imports numpy and hmmlearn lazily.

Example outline:

    from research.labs.regime_hmm import features_from_closes, train_gaussian_hmm
    features = features_from_closes(closes, window=14)
    # Slice chronologically BEFORE training. Never fit on the full dataset.
    train_rows = features[:500]
    test_rows = features[500:550]
    fit = train_gaussian_hmm(train_rows, n_states=3)
    filter_ = fit.new_alpha_beta_filter(alpha=0.05, beta=1.0)  # placeholder values; tune only on training/validation
    for row in test_rows:
        signal = filter_.update(row)  # one call per completed candle, in order
        print(signal.regime, signal.confidence, signal.normalized_entropy)

This is only a mechanics demo. Alpha and beta shown are placeholders, not tuned values. It does not estimate strategy P&L, include contract-specific payout mechanics, establish net edge, or demonstrate live readiness.

## Promotion gates — not yet satisfied

- Compare to a no-regime-filter baseline and simple non-HMM controls. A model is useful only if it improves cost-adjusted outcomes out of sample.
- Research targets previously discussed for this project (PF > 1.5 and net expectancy > 0.15R) are screens, not automatic promotion rules. Sample size, calibration, stability across chronological folds, multiple testing, and sealed prospective OOS must also pass.
- Separately evaluate (a) block entry, (b) no size change, and (c) a proposed 50% size reduction. Do not assume the 50% cut improves net edge or drawdown. UNDEFINED should be treated as an unqualified strategy candidate in research; it must not trigger a global account kill switch by itself.
- No Layer 6 integration is included. Any future integration must use the existing deterministic risk authority, preserve strategy/account limits, define stale/missing/model-error handling, and have explicit tests plus independent review.
- DTW/K-Shape pattern clustering is deferred until regime labels show stability and incremental value over baseline controls. Otherwise, clustering increases the multiple-testing/overfitting surface without evidence of benefit.

## Source references

- Sui, Pu, Leng, Vlaski, Alpha-Beta HMM, arXiv:2504.01759: https://arxiv.org/abs/2504.01759
- Deriv API, Ticks History: https://developers.deriv.com/docs/data/ticks-history/
- hmmlearn API: https://hmmlearn.readthedocs.io/en/0.3.3/api.html
