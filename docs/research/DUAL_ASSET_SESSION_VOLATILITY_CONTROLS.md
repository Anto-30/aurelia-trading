# Dual-asset session and volatility controls (research only)

## Status and scope

This change adds reusable research controls and a pre-simulation adapter for AURELIA's existing research candidate contract. It does not add a second strategy engine, broker interface, capital authority, or live configuration. All outputs carry research-only authority flags. `config/LIVE_LOCK.yaml` is unchanged.

The repository does not currently contain the prompt's named `MSNRTradeSimulator`, `layer9/falsification_tests.py`, or `config/live_gates.yaml` paths. The canonical research detector is `research/labs/deterministic_intraday_strategies.py`; the candidate sizing adapter accepts its `StrategyCandidate` contract. It can be called by a future research simulator, but it is not evidence that a complete MSNR backtest simulator exists.

## Asset-class routing

### Financial FX

The classifier uses local IANA time zones, not permanently fixed UTC offsets:

| Label | Local window | Zone |
|---|---|---|
| ASIAN | 09:00–16:00 | Asia/Tokyo |
| LONDON | 07:00–10:00 | Europe/London |
| NY_AM | 08:30–11:00 | America/New_York |
| NY_PM | 11:00–19:00 | America/New_York |
| DEAD | all remaining timestamps | — |

The Tokyo window corresponds to 00:00–07:00 UTC. London and New York windows shift in UTC when their respective daylight-saving rules change. Timestamps must be timezone-aware. During the Tokyo/London overlap, LONDON takes precedence so every financial timestamp receives one exclusive label.

The 2:33 AM and 4:15 AM times from the supplied cheat sheets are not encoded. Neither is treated as a trading trigger. The London window remains a hypothesis and must pass Test C on sealed, source-verified FX data.

### Deriv synthetic indices

The classifier returns `SYNTHETIC_BYPASS`; `is_kill_zone` returns an all-true mask, so no synthetic bar is excluded by session time. This is consistent with Deriv's description of synthetic indices as 24/7, CSPRNG-generated products that are not affected by regular market hours or real-world liquidity. It does not prove that every possible intraday pattern is absent; any discovered periodicity would need a separately registered, multiple-testing-aware falsification test and must not be explained as London liquidity without evidence.

The volatility sizer may still operate on synthetic strategy returns as a variance-control experiment. That is not market-liquidity modelling and is not a claim that the Moreira–Muir result transfers to synthetic indices.

## Volatility sizing

`VolatilitySizer` provides two causal estimators:

- `rolling`: sample standard deviation of the previous `window` completed returns.
- `ewma`: exponentially weighted variance of previous completed returns, with configurable decay.

The default adapted scaling rule is:

`raw_multiplier = target_vol_annual / prior_realized_vol_annual`

It is clipped to [0.10, 3.00]. The final risk fraction is additionally capped at 2% of the sizing base. Thus a 1% base risk and a 3.0x clipped multiplier do **not** produce 3% risk; the effective risk is capped at 2%.

The periods-per-year value is mandatory because annualization depends on sampling frequency. 252 is appropriate only when the input return observations are daily FX observations under a 252-session convention. It must not be copied into M1/M15 or 24/7 data. Use the actual observation frequency and document the convention for each dataset.

Sizing is lagged: schedule point `i` is calculated from `returns[:i]`; the current bar's return is not available to size a trade at that bar. Insufficient warm-up, zero volatility, or an invalid estimate blocks that trade. It does not fall back to base risk.

Every accepted research candidate can produce an audit record with the estimator, realized volatility, raw/clipped/effective multiplier and final risk fraction. The adapter does not send orders or modify Layer 6.

## Relationship to Moreira and Muir (2017)

Moreira and Muir's published portfolio construction scales monthly factor returns by the inverse of the **prior month's realized variance**, then normalizes the managed portfolio to match the original portfolio's unconditional variance. Their study includes equity factors and currency carry. The study's empirical finding is not proof that a simple inverse-standard-deviation rule improves a specific intraday MSNR strategy, and it is not evidence for Deriv synthetic indices.

This module is an operationally bounded inverse-standard-deviation adaptation: it uses an explicit target, caps the multiplier, caps the final risk fraction, and does not perform the paper's unconditional-variance rescaling. It should be compared against an unscaled baseline and the inverse-variance formulation in future research before any selection is made. Rolling versus EWMA is itself another registered model comparison.

The current repository does not expose a canonical Deflated Sharpe Ratio calculation. `select_volatility_estimator_from_dsr` therefore accepts externally calculated DSR values and refuses to choose when they are missing or trade counts are insufficient. It requires the caller to include at least both estimator configurations in the multiple-testing count; the supplied DSR must already account for the full registered search family. The function does not calculate or fabricate DSR.

## Test C: session-window edge

`test_c_session_edge` is financial-only. For synthetic indices it returns `SKIPPED`. Inputs are net trade R values grouped by calendar day for LONDON, NY_AM, ASIAN and BASELINE. Empty days must be retained so the moving-block bootstrap respects calendar-time clustering.

The test requires at least 100 trades per group and 30 daily observations. It applies a deterministic circular moving-block bootstrap and reports expectancy, profit factor, trade count and 95% intervals. It passes only when London's lower 95% bound exceeds both the baseline upper bound and the Asian upper bound, and London's lower bound is positive. This non-overlapping-CI rule is deliberately conservative; it is not a substitute for reporting a direct bootstrap confidence interval on the pairwise expectancy differences.

NY_AM results are reported for comparison, but the pre-registered London hypothesis is not replaced with NY_AM or another window if London fails. The 2:33/4:15 claims remain untested unless separately registered.

## Integration boundaries and remaining work

- The candidate adapter receives an existing research-only candidate, the signal timestamp, the entry-bar index and the lagged sizing schedule. It returns a research allow/deny decision and risk fraction. A full trade simulator must still model next-bar fills, gap-through stops, stop-first OHLC ambiguity, itemized spread/slippage/fees, end-of-data handling and the relevant product's actual payoff mechanics.
- The generic OHLC replay in the repository expressly is not a Deriv contract-payout model. Do not use price-difference P&L as realized Deriv Options/Multipliers economics.
- The repository's canonical release/evidence gates remain authoritative. These modules do not add a parallel `live_gates.yaml`, do not change the strategy registry's qualification status, and cannot move `LIVE_LOCK`.
- No historical FX data, synthetic-index data, costs, bootstrap results or DSR values are included in this PR. Unit-test fixtures are not market evidence.
- A session-edge failure means discard the London filter for that registered strategy/data scope. It does not authorize retuning the same sealed OOS data to find a different time window.
- A positive research result is still not a live authorization. Verified instrument specification, cost economics, walk-forward/OOS validation, independent review, operational soak, deployment verification and human release authorization remain separate requirements.

## Official and academic references

- Deriv, [Synthetic Indices](https://deriv.com/markets/derived-indices/synthetic-indices): CSPRNG generation, 24/7 availability, and no dependence on regular market hours or real-world liquidity.
- Moreira and Muir, [Volatility-Managed Portfolios](https://www.nber.org/papers/w22208), NBER Working Paper 22208 (2016); published in *The Journal of Finance* 72(4), 1611–1644 (2017), DOI 10.1111/jofi.12513.
