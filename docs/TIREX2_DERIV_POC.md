# TiRex-2-like Deriv PoC — synthetic coupling and latency only

## Scope and gate

This is an isolated research utility, not a Layer 9 integration. It has no Deriv client, capital-plane import, signal output, order path, or LIVE_LOCK mutation. The repository's existing live controls remain unchanged: VERIFY_ONLY, LIVE_EXECUTION blocked, and final execution authorization false.

The first PoC phase is limited to reproducible synthetic multivariate samples from independent univariate price histories and measured TiRex-2 forecast latency on the intended deployment machine. It does not train a model, establish alpha, compare Sharpe, or authorize trading.

## Input contract

Supply a long-format CSV with columns timestamp,symbol,close by default. Timestamps must be UTC-aware ISO-8601 or Unix epoch seconds. Each symbol must be strictly chronological with no duplicates, finite positive prices, and exactly the configured bar cadence. The default is 60 seconds; set 900 for 15-minute bars. Gaps fail instead of being silently bridged. Volume, order-book fields and future-known covariates are not used.

## Synthetic coupling

Run from the repository root:

    python -m research.labs.tirex2_synthetic_coupling --csv /path/to/prices.csv --output-dir /path/to/new-run --context-length 128 --horizon 1 --variates 3 --samples-per-split 1000 --seed 7 --expected-interval-seconds 60

The tool creates coupled_samples.jsonl and manifest.json only if train, validation and test each have at least `--variates` distinct series with eligible windows. For `context_length=128` and `horizon=1`, every split needs at least 129 contiguous observations for each participating series; with a 70/15/15 time split, plan for roughly 860 or more observations per symbol, with additional margin for gaps or unequal histories. The CLI fails with an explicit “no eligible windows” error when a split is too short. Time boundaries are assigned before sampling and context/target windows cannot cross a split. Windows from separate symbols are sampled independently and may have different timestamps: this is a synthetic pretraining/data-pipeline experiment, not evidence that R_100 and other synthetic indices are real causal covariates. If there are too few series, the pipeline fails rather than duplicating a series or inventing covariates.

The manifest records input and output SHA-256 hashes, split boundaries, seed, window counts, sample counts, restrictions and explicit RESEARCH_ONLY status. Sample contents are reproducible with the same input, arguments and seed; the manifest creation timestamp naturally changes.

## Local inference latency

The TiRex-2 extra is optional. Install with: pip install '.[tirex2]'. The checkpoint may require Hugging Face access/acceptance. Authenticate outside this repository using the supported login flow; never put tokens in code, CSVs, shell history or artifacts. Pin an immutable model revision when collecting comparable evidence.

For univariate 1-minute bars:

    python -m research.labs.tirex2_latency_benchmark --csv /path/to/prices.csv --symbols R_100 --context-length 128 --prediction-length 1 --device cpu --warmup 10 --runs 1000 --revision FULL_40_CHARACTER_MODEL_COMMIT_SHA --latency-budget-ms PRE_REGISTERED_P99_BUDGET_MS --expected-interval-seconds 60

For 15-minute bars, set the interval to 900. Multi-series stress testing can select comma-separated symbols only when the latest contexts align exactly; the benchmark will not fabricate timestamps. Such a run measures multivariate inference cost, not whether those symbols should be used as live covariates.

The report separates CSV/context preparation, model loading, input construction, the first forecast call (which may include initialization/compilation), and warmed p50/p95/p99/max latency. A p99 PASS/FAIL verdict is issued only when a positive budget is supplied, `--revision` is a full 40-character hexadecimal commit SHA, and at least 1,000 warmed measurements are collected. Short smoke runs remain usable for diagnostics but return `NOT_EVALUATED_INSUFFICIENT_SAMPLES`; an unpinned or mutable model revision returns `NOT_EVALUATED_UNPINNED_MODEL_REVISION`. Without a frozen budget, status is `NOT_EVALUATED_NO_FROZEN_BUDGET`. Measurements include input-object construction and local model forecasting, but exclude Deriv networking, strategy logic, Layer 6, and broker execution. They are not end-to-end trading latency.

## Gates before any Layer 9 proposal

1. Confirm input hash, symbol/timeframe, history coverage, gap policy and immutable model revision.
2. Run unit tests and inspect the manifest; leakage, timestamp gaps, duplicate rows, insufficient series per split or mismatched provenance are no-go conditions.
3. Freeze the p99 budget before testing the intended hardware. Capture hardware/software versions, first-call timing and warmed percentiles; repeat after restart and with the intended backend.
4. Do not infer strategy performance from forecast speed. A later phase must compare MSNR with a pinned challenger using chronological walk-forward/OOS validation, cost-adjusted Deriv contract economics, calibration, regime segmentation and uncertainty intervals.
5. Keep the model in RESEARCH. No promotion, live feature route, execution authorization or capital-plane integration is part of this PoC.

## Upstream references

- TiRex-2 source: https://github.com/NX-AI/tirex-2
- TiRex-2 documentation: https://nx-ai.github.io/tirex-2/
- TiRex-2 paper: https://arxiv.org/abs/2607.01204
