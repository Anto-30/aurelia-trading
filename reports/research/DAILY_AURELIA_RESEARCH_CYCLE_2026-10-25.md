# AURELIA Daily Research & Training Cycle — 2026-10-25

**Classification:** RESEARCH_ONLY · Evidence review, not a trading signal or release certification  
**Disposition:** BLOCKED for strategy qualification; no strategy promoted  
**Safety invariants:** No orders submitted. No secrets accessed or written. `config/LIVE_LOCK.yaml` was read only and was not changed.

## 1. Executive result

The highest-value result of this cycle is not an alpha claim: the current R_100 research pipeline is not producing trustworthy, continuous observations, and the canonical repository's readiness snapshot is stale. Training, parameter search, Monte Carlo, or strategy ranking by profitability would be misleading until data integrity and contract economics are established.

The current main branch is `d04564aca0648201feff0326fe9af0fbcee92e94` (commit time 2026-10-18T14:34:26Z). The scheduled R_100 prospective-OOS workflow ran on 2026-10-24 and failed during collection with `DerivTransportError: {'code': 'TRANSPORT_READER_FAILED'}`. Its collector tests passed and its state artifact was uploaded, but the run is **not** a strategy-validation pass. The workflow reported `R100_COLLECTION_EXHAUSTED=1 state_preserved_for_next_run=true`.

A separate non-production control-path soak completed successfully: 3,600 seconds, 720 health checks, 3 controlled restarts, and zero health-check failures. The evidence explicitly classifies this as `SIMULATION_VERIFIED`, with no authenticated Deriv session and no capital movement. It is not a production soak or broker-lifecycle certification.

## 2. Canonical safety state and lineage

### Canonical source identity

- Repository: `Anto-30/aurelia-trading`
- Branch: `main`
- Main commit: `d04564aca0648201feff0326fe9af0fbcee92e94`
- `AURELIA_SOURCE_OF_TRUTH.json` blob: `fec9ba04d7898884b0940555b023d46fd1413ea8`
- `config/LIVE_LOCK.yaml` blob: `b2cddd1efb0f25f35a6a08354290f805812bf34c`
- `config/strategy_registry.json` blob: `6700bd62a9a3ebc3e4ead69f16ca4fd4740d3b3b`
- `config/runtime.yaml` blob: `58af42017bfe6d37b0b590edefdf9a65490a8654`
- `research/r100_prospective_oos_collector.py` blob: `e02a21e63ab12ea81eab2da3af12f12e9da4977b`
- `runtime/validation/probability.py` blob: `c67f7e7833c31b780ed815bea7f3999a13ac31e7`
- `runtime/validation/walk_forward.py` blob: `6a6df51285d6ecf75da7b98cf97b1e0f68a53317`

### LIVE_LOCK state observed

`live_trading_enabled=false`, `FINAL_EXECUTION_AUTHORIZATION=false`, `LIVE_EXECUTION=BLOCKED`, `capital_plane_mode=VERIFY_ONLY`, `research_capital_authority=false`, `external_repositories_capital_forbidden=true`, `blind_resubmission=false`, `kill_switch_independent=true`.

This cycle did not modify the lock. No workflow approval or release-gate bypass was attempted.

### Readiness evidence is stale

`data/runtime/AURELIA_READINESS.json` identifies itself as generated on 2026-10-03 and says its evidence is not authoritative until regenerated against the current commit. It records no configured authenticated Deriv session, no fresh balance, no real-broker evidence, and incomplete prospective OOS, calibration, economics, deployment, and soak certification. `data/runtime/AURELIA_EXTERNAL_ACCESS_STATE.json` is a 2026-10-05 snapshot and is also historical, not current proof. The current branch-protection endpoint could not be verified in this audit (GitHub returned 403); an older snapshot is not sufficient to assert current protection state.

### Workflow evidence

1. **R_100 prospective-OOS run #299** — [run 40136259228](https://github.com/Anto-30/aurelia-trading/actions/runs/40136259228), main SHA `d04564aca0648201feff0326fe9af0fbcee92e94`: collector tests passed; collection failed with `TRANSPORT_READER_FAILED`; state-preservation path ran; artifact ID `12576759759`; uploaded ZIP SHA-256 `58a20975ccddfa1f47f36ea3a9337c5f0b07fad933c4f864a2048afc9661c57b`. The campaign's logged frozen code commit was `67922e738acd06e9f77d434819df1a56aa11974d`, which must not be confused with the workflow's main head. The archive's internal dataset hash/config hash/row count were not independently extracted during this cycle; those fields remain unverified here.
2. **Non-production 3,600-second soak** — [run 40133999634](https://github.com/Anto-30/aurelia-trading/actions/runs/40133999634), main SHA `d04564aca0648201feff0326fe9af0fbcee92e94`: 3,600 seconds, 720 checks, 3 controlled restarts, 0 health-check failures; artifact ID `12577663240`; uploaded ZIP SHA-256 `2e07b2b86100bbfcf2ef725aed29f333708135056e184744868128e2187041ba`. Classification: non-production simulation only; capital could not open new exposure.
3. **Research unit tests on draft PR branches:** the current #203 range-validation head and #205/#206 research-fix heads have successful unit-test runs. These verify the tested code paths on those isolated commits only. They do not qualify a strategy, prove valid historical coverage, or replace the pending protected assurance gate. Several assurance jobs remain `waiting` for protected-environment review; this cycle did not approve them.

## 3. Market and macro intelligence (context only)

### Cross-market snapshot

The latest available Alpaca IEX daily bars were dated 2026-10-23, the last U.S. session available to this Sunday review. Compared with the prior daily bar, approximate closes changed as follows: broad U.S. equity proxy -0.55%, technology-heavy equity proxy -0.05%, small-cap proxy -0.33%, gold ETF -0.67%, silver ETF -1.26%, and oil ETF +4.34%. These are IEX-feed daily-bar comparisons, not executable quotes. The returned GLD and USO bid/ask snapshots were abnormally wide; they are excluded from spread, liquidity, and execution-cost inference.

A public-market report dated 2026-10-23 described a sharp technology-stock selloff, concerns about debt-financed AI capital expenditure, higher geopolitical risk, Brent crude above $113/barrel, and U.S. 10-year Treasury yields near 5%. These are relevant macro risk factors for conventional markets, but they are **not evidence of a causal signal in Deriv synthetic indices**. Treat them as contextual flags only.

The crypto-market overview connector returned a snapshot with total market capitalization around $2.69T, 24-hour volume around $60.9B, and a Fear & Greed reading of 45 (Neutral). Its accompanying news timestamps were on 2026-10-24; this is a stale context snapshot rather than a fresh Oct-25 tick-level input.

The connected macro-data API failed because its available credit balance was $0, and the connected broad-market-news API returned Unauthorized. Public web sources were used as a fallback. No unavailable macro series or API output has been fabricated.

Sources:
- Official Deriv `ticks_history` schema: https://developers.deriv.com/docs/data/ticks-history/
- Deriv product updates (2026-08-10 symbol additions): https://developers.deriv.be/product-updates/
- Financial Times market report (2026-10-23): https://www.ft.com/content/6e318b81-a771-4842-9754-e265fef2852f
- Business Insider market report (2026-10-22): https://www.businessinsider.com/stock-market-today-tech-sell-off-meta-tesla-oil-prices-2026-10
- Deflated Sharpe Ratio paper (selection bias and non-normal returns): https://doi.org/10.3905/jpm.2014.40.5.094

## 4. Ranked hypotheses and agent routing

Ranks below are **research priority**, not estimates of profitability. No new backtest, training run, parameter search, or Monte Carlo result was generated because trustworthy Deriv observations and observed contract economics are not currently established.

| Rank | Hypothesis / domain | Assigned role(s) | Experiment and acceptance criteria | Current status |
|---|---|---|---|---|
| P0 | **H-DATA-001 — feed integrity and transport continuity** | ClaudeCode (repair); JEV (independent validation); KimiK3 (adversarial review) | Reproduce reader failure; preserve the raw response and transport cause; bounded reconnect/backoff; strict symbol, epoch, timestamp, numeric, and continuity checks; prove a failed request cannot become a valid observation. | **BLOCKED / highest priority.** Main prospective collector fails with `TRANSPORT_READER_FAILED`. |
| P1 | **H-R100-TICK-MOMENTUM-001 — normalized tick-return shock** | KimiK3 (quant lead); ClaudeCode (collector); JEV (independent evidence review) | Existing frozen campaign: strategy `R100_TICK_MOMENTUM_PROSPECTIVE_V0.2.0`; window 64; minimum observations 20; threshold 1.5; cooldown 30 seconds; horizon 10 ticks; one declared trial; no retuning after collection begins; probability interval 0.55–0.75, no clipping. Require a valid sealed prospective dataset, costs, calibration, and at least 100+ OOS observations/trades per applicable strategy × symbol × regime cell. | **UNQUALIFIED.** Collection failed. No performance conclusion. Campaign dataset/config hash and row count were not independently extracted in this cycle. |
| P2 | **H-REGIME-001 — regime-conditioned trend/momentum versus mean reversion** | KimiK3; GrokBot for contextual regime/news synthesis; JEV review | Compare a simple deterministic baseline against a predeclared regime filter (e.g., rolling volatility/trend state or HMM/Alpha-Beta candidate). Use lagged features only. Regime state is a conditioning variable, not an automatic trade signal. | **NOT RUN.** Requires valid tick/candle data, frozen feature definitions, and sealed OOS. |
| P3 | **H-MSRN-001 — market-structure / liquidity-sweep / FVG continuation or rejection** | KimiK3; ClaudeCode; JEV | Use closed OHLC bars, confirmed swing points, verified tick size, exact UTC windows, and next-bar execution timing. Test liquidity-sweep and fair-value-gap geometry separately before combining. Reject any unsupported DOM, order-book, delta, or CVD feature. | **NOT QUALIFIED.** Instrument mapping, history integrity, and observed cost profile remain unresolved. |
| P4 | **H-CONSOL-001 — rolling consolidation breakout** | KimiK3; JEV | Define compression from trailing range/ATR, require a closed-bar break, enter no earlier than the next bar, and compare breakout against a no-filter baseline. Use an opening-range definition only where a real session open/time zone is verified; otherwise test a rolling consolidation window for 24/7 synthetic indices. | **NOT RUN.** Session semantics and source integrity not verified end-to-end. |
| P5 | **H-VOL-MR-001 — volatility-conditioned mean reversion versus trend following** | KimiK3; JEV | Predeclare volatility buckets and separate trend/mean-reversion hypotheses. Use block bootstrap or another dependence-aware Monte Carlo design, cost stress tests, ablation, and local parameter sensitivity. Do not optimize thresholds on the reserved OOS window. | **NOT RUN.** No trustworthy sample available. |
| P6 | **H-MTF-001 — multi-timeframe confirmation** | KimiK3; ClaudeCode; JEV | Align 1s/tick, 1m, 5m, 15m, 30m, 1h and 4h features only after their timestamp semantics are verified. Compare incremental value against a single-timeframe baseline; avoid future-bar leakage and duplicate correlated features. | **NOT RUN.** Requires clean synchronized observations and explicit feature availability times. |
| P7 | **H-ML-001 — ResNet-LSTM / learned feature interaction** | KimiK3; ClaudeCode; JEV | Keep `RLSTM-IBTI-v0.1` in RESEARCH. Start with deterministic baselines and a small feature set (returns, candle geometry, lagged timing, rule state, residuals, regime). Freeze preprocessing and labels; report feature/seed/search lineage; require OOS economics and calibration before considering shadow evaluation. | **RESEARCH ONLY.** No training was performed; the current registry records no qualification evidence. |
| P8 | **H-VWAP-001 — VWAP pullback/reclaim** | KimiK3; JEV | Do not treat tick count as exchange volume. Test only if the exact instrument/feed supplies a verified session-volume definition; otherwise reject this feature family for that instrument. | **REJECTED FOR NOW** on unverified session volume; no OOS/cost evidence. |

### Coverage across requested domains

- **Market intelligence, global macro/news, cross-market relationships:** reviewed as contextual risk inputs only; never used as an entry trigger for a synthetic index without empirical evidence.
- **Market structure, liquidity, fair-value gaps, opening-range/consolidation breaks:** price-geometry hypotheses only; no order-book/depth/DOM/CVD assumptions unless the source explicitly supplies the required observations.
- **Trend, momentum, mean reversion, volatility, tick dynamics, multi-timeframe analysis:** independent hypotheses with frozen baselines and lagged features; no indicator stacking before ablation.
- **Microstructure:** quote/tick arrival, spread only where bid/ask are valid and feed coverage is adequate, price changes, gaps, latency, and reconnect effects. Tick imbalance is not order-flow imbalance; tick volume is not traded volume.
- **Machine learning and feature engineering:** no model training until data integrity, label timing, leakage controls, and baseline performance are verified.
- **Probability calibration and uncertainty:** report Brier score, log loss, reliability bins, sample count, uncertainty intervals, and drift. The existing collector specifies at least 3 buckets, 10 observations per bucket, and maximum reliability gap 0.05; these are minimum diagnostics, not proof of statistical sufficiency.
- **Position sizing, drawdown and tail risk:** no stake recommendation while balance, account currency, contract maximum loss/payout, and observed economics are unavailable. Preserve the existing <=1% planned-risk default and <=2% absolute cap; do not infer affordable stake from stale balances.
- **Execution costs:** measure observed contract economics and actual realized cash flows. Do not substitute assumed linear multipliers, generic pips, or unverified spread/slippage for a Deriv contract payout model.
- **Walk-forward/OOS, Monte Carlo, ablation, parameter sensitivity, multiple testing:** require frozen splits, data hashes, seeds, trial counts, selection rules, cost stress, dependence-aware resampling, feature ablations, and a reserved OOS window. Use deflated-Sharpe / backtest-overfitting controls and multiple-testing corrections as diagnostics, not as guarantees.
- **Strategy retirement/revalidation:** suspend or retire a candidate if net expectancy is non-positive under observed costs, data provenance breaks, calibration becomes stale/drifted, drawdown limits breach, OOS performance degrades materially (the draft Layer-6 research metric uses a 30% degradation rejection rule), or the instrument/contract specification changes. Revalidation must create a new lineage record; never overwrite the prior result.

## 5. Engineering and risk findings

### P0 — fix data integrity before any alpha work

1. **Transport failure is not a strategy result.** Diagnose `runtime/adapters/deriv_ws.py` reader failure. Add bounded retry/reconnect and preserve the original failure context; if the source remains invalid, exit non-zero and preserve state. Do not silently turn a transport failure into an observation.
2. **Reject out-of-window history.** Draft PR #203 documents a public historical request for an R_100 candle window anchored at 2022-10-21 returning an epoch in 2026, outside the requested interval; the response was correctly rejected and its raw response hash was recorded. The official schema should be enforced, and any candle outside the requested half-open interval must fail the batch rather than be silently filtered.
3. **Make time windows exact.** Draft PR #205 defines `[2022-10-21T00:00:00Z, 2024-10-21T00:00:00Z)` and rejects extra source candles. Preserve that half-open UTC boundary in the manifest and simulator.
4. **Require observed economics.** Draft PR #206 adds a fail-closed requirement for an observed `config/COST_MODEL.json` reconciled against a statement or profit-table artifact, with contract type/currency, sample count, gross PnL, realized net PnL, known fees, residual tolerance, and a source hash. Until this exists, do not produce a qualified trade ledger or infer edge from a linear proxy.
5. **Reconcile the research PR stack before merging.** #190 is based on the #188 research baseline; #203 builds on #190. Separately, #205 is based on #188 and #206 builds on #205. Review/rebase these changes as one coherent history-validation/economics sequence so a dependent fix is not merged without its prerequisite. Keep all of them research-only.

### P1 — reconcile policy and validation contracts

6. **Probability-floor conflict:** `config/runtime.yaml` and `runtime/core/authority.py` use 0.50, while the continuous research/operations policy declares 0.55. The current registry also requires calibrated, fresh, drift-cleared probabilities. Resolve the intended hard floor in one canonical policy and add tests across config, runtime, and research code. Do not silently choose a value or weaken a gate during this cycle.
7. **Capital-floor conflict:** `config/runtime.yaml` / `AURELIA_SOURCE_OF_TRUTH.json` specify a $100 minimum available balance for a $1 starting stake, while the readiness orchestrator's minimum-capital gate is $1.50. Establish one authoritative floor and test all readiness, stake-sizing, and account-currency paths. Until reconciled, treat capital affordability as UNKNOWN.
8. **Drawdown-policy precedence:** the research contract-debate primitive uses a 3% drawdown breaker, while the broader system directive has a 15% maximum-drawdown halt. These may be different layers, but the precedence and semantics must be explicit. The contract-debate policy also uses a 2% payout-change threshold over 500 ms; that is not the same metric as the separate <=1% payout-slippage requirement. Keep both metrics distinct and test them separately.
9. **Calibration input validation:** `runtime/validation/probability.py` validates probability range but does not explicitly require outcomes to be finite binary labels. Invalid/non-finite outcomes can yield misleading metrics; `detect_drift` also lacks explicit finite-input validation. Small repair: reject non-binary/non-finite outcomes and invalid reference/current means; make invalid drift inputs fail closed; add regression tests.
10. **Promotion evidence semantics:** `runtime/strategy/governance.py` currently checks that evidence IDs and an approver string are non-empty. Verify call sites and ensure this helper cannot be mistaken for the deterministic release gate. If it is used to advance qualification state, require current, schema-valid evidence and a gate verdict rather than non-empty strings alone.
11. **OOS validator scope:** `runtime/validation/walk_forward.py` checks sealing, retuning, and minimum trade count. It is a helper, not a complete qualification engine: it does not itself verify dataset/config hashes, date boundaries, observed economics, calibration, multiple testing, or strategy registry evidence. Keep the full release decision conjunctive and separate.
12. **Archive validation:** `research/r100_prospective_oos_archiver.py` checks a sealed flag and row hash; add explicit schema, manifest, row-count, timestamp, and required-field validation before an archive is accepted as qualification evidence.
13. **Stale readiness:** regenerate `AURELIA_READINESS.json` only from the current assurance/evidence pipeline. Do not hand-edit the historical snapshot into a pass.
14. **Secret isolation:** draft PR #202 separates public assurance from protected Deriv verification. Review the exact workflow diff and retain the production environment only on the privileged verification job. Protected assurance is still pending; do not approve it as a shortcut.

## 6. Experiment-lineage contract

Every new experiment must record:

- hypothesis ID and explicit null/baseline;
- exact symbol/instrument ID, contract type, currency, timeframe and timestamp convention;
- raw-data source, request parameters, collection interval, row count, continuity checks and SHA-256 hashes;
- code commit, strategy/model version, config hash, dependency lock and runtime identity;
- random seeds, feature definitions, label horizon, search space, trial count and selection rule;
- IS/WFA windows, sealed untouched OOS window, OOS reuse count and minimum sample requirement;
- gross and net results, observed costs, uncertainty intervals, calibration/drift metrics, drawdown/tail metrics, ablations and parameter-sensitivity results;
- reviewer identity, limitations, rejection reason, and immutable artifact IDs/digests.

For this cycle, the existing prospective campaign's frozen parameter set and campaign code commit were observed, but the internal data/config hashes and row count were not independently extracted. Those fields are **UNKNOWN**, not inferred from the uploaded ZIP digest. New hypothesis trials this cycle: **0**. No model was trained, no OOS metric was calculated, and no strategy was promoted.

## 7. Agent routing and execution truth

The repository's routing policy assigns:
- **GrokBot:** orchestration, market/news synthesis, blocker diagnosis and ranked queue.
- **KimiK3:** quant hypothesis design, walk-forward/OOS, calibration, multiple testing and adversarial counterexamples.
- **ClaudeCode:** transport/API/data-pipeline engineering, tests, CI and smallest-change repairs.
- **JEV:** independent evidence, regression and release-gate audit.
- **GoogleAgentSkills:** security, least-privilege and cloud/agent-boundary review.
- **GLM:** evidence/artifact inspection and discrepancy reporting.
- **PlaywrightCLI:** browser/session/network verification when a UI path is actually needed.
- **AURELIA:** deterministic risk/capital controls only; no external agent receives capital authority.
- **ChatGPT:** supervisory research and independent cross-check; this cycle's repository/data-source inspection and synthesis were performed here.
- **Dev:** blocked in the repository policy because no authorized development device/runtime is connected.

The available ChatGPT skills registry returned no installed skill entries. The repository has a draft PR registering DeepSeek Harness as a quant-validation role, but this cycle did not have an independently verified DeepSeek runtime or execution proof. No external agent is represented as having run merely because it is registered in configuration.

## 8. Exit criteria for the next cycle

1. Diagnose and reproduce the R_100 reader failure; capture the full root cause and a deterministic regression test.
2. Reconcile the #188/#190/#203 and #188/#205/#206 dependency stacks; verify the current Deriv schema and exact half-open windows.
3. Obtain valid public tick observations prospectively and confirm source, timestamps, symbol, continuity and manifest hashes. Do not reuse invalid historical responses.
4. Require observed contract-specific economics before calculating qualified expectancy or profit factor.
5. Reconcile probability floor, capital floor, drawdown, and payout-slippage policy conflicts in a reviewed, test-backed change.
6. Validate calibration input handling and evidence semantics; independently review the fix.
7. Preserve the 3,600-second non-production soak evidence, but keep production soak and authenticated broker lifecycle marked NOT RUN.
8. Re-run walk-forward, sealed OOS, calibration, cost stress, Monte Carlo, ablation, parameter sensitivity and multiple-testing controls only after data/economics gates pass.
9. Keep all strategy registry entries RESEARCH_ONLY / UNQUALIFIED until the complete deterministic release gate passes.

**Final disposition:** continue research, but fail closed. The non-production soak is a valid control-path result; it is not a strategy edge. The R_100 collection failure and missing observed economics block a defensible trading-performance conclusion.
