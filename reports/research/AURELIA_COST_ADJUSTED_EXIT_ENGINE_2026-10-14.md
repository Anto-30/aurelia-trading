# AURELIA cost-adjusted exit research harness — implementation note

Date: 2026-10-14
Base branch: main
Base commit: 89ea6bb67443f2922b57ac61ea48fcf9bc9f00af
Status: research-only; not merged; no live authority.

## Scope

Adds a pure research-plane comparison harness for identical entry-path replay. It evaluates 1:1, 1:1.25, 1:1.5, 1:1.75, 1:2, 1:2.5 and 1:3 fixed targets, a 2R target with break-even movement, a trailing-stop candidate, and a time stop. Initial planned risk remains the denominator for every R-multiple. The path contract requires a verified instrument-spec reference, data hash, exact entry ID, timestamps, account currency and an explicitly declared linear R-path payoff model.

The harness uses conservative stop-first handling when OHLC data cannot resolve a same-bar collision; adverse stop gaps fill at the bar open; a target gap gets no favourable improvement. Stop changes observed at a bar close affect the next bar. Costs record source type, reference, timestamp, currency, confidence, limitations and cash amount. Required cost-component names are declared per instrument/profile; a result cannot be marked cost-complete if a required component is absent. Explicitly embedded costs are not deducted twice. Result rows retain cost-source references and limitations, list source classes, and always mark production cost qualification false. Mixed strategy/instrument/timeframe/regime/spec samples are rejected. Freshness/effective-period approval of external cost profiles remains a separate qualification gate. Unknown required costs cause COST_INCOMPLETE, and net expectancy / net profit factor / net confidence interval are withheld.

The evaluator has no signal-generation, stake-sizing, capital authority, live-order or broker-submission behavior. It intentionally rejects fixed-payout payoff models. Partial exits, native contract lifecycle simulation, instrument adapters, and data ingestion are not implemented in this first slice.

## Evidence-based R100 finding

Source evidence: public Deriv R100 prospective-OOS workflow run 38554782088 (https://github.com/Anto-30/aurelia-trading/actions/runs/38554782088), downloaded artifact ID 11890351692, artifact archive hash 5d3825ba83fe767c42d2d664830010d1458bcd2458b90abb41afca3c28cf4eaf. The campaign strategy configuration commit is 67922e738acd06e9f77d434819df1a56aa11974d; the workflow ran against main commit 89ea6bb67443f2922b57ac61ea48fcf9bc9f00af.

The artifact's frozen chronological cutoff is 2026-10-09T19:20:38.482344Z. Independent recomputation from raw records gives 170 in-sample and 518 out-of-sample observations, 261 OOS wins, and a 50.3861% OOS win rate. All 518 OOS signal IDs have observed proposal quotes at a payout/stake ratio of 1.95. The fixed-payout gross economics are +0.95 stake on wins and -1.00 stake on losses, implying a no-extra-fees break-even win rate of 51.2821%. The observed quote-based mean is -0.017471 stake per trade (-1.7471% per stake), matching the report. A circular moving-block bootstrap (block length 5, 10,000 replicates, seed 20261014) gives a 95% interval of approximately [-0.1041, +0.0691] stake units per trade; it includes zero and is sensitive to block assumptions.

The R100 strategy remains ECONOMICS_FAILED and not live eligible. The report labels realized costs unknown and realized execution not measured. Its underlying directional mean is not the fixed-payout contract P&L. Probability calibration is provisional (Brier 0.2721, max reliability gap 0.1687, only two buckets with at least 10 samples); no calibration or execution qualification is claimed. The campaign is incomplete and this evidence does not test stop/target paths.

## Verification

Locally executed in a scratch test workspace, without network access or broker submission:

- PYTHONPATH=/tmp/aurelia_rr python -m unittest research.labs.tests.test_risk_reward_experiments tests.test_trade_economics_master_example -v
- 15 tests passed locally before the final required-cost/provenance refinements. The exact latest PR commit is tested by GitHub Actions; do not treat this scratch run as a local test of that newer revision.
- This run tests the new research harness and a scratch copy of the currently inspected runtime/core/economics.py; it is not a full repository suite or production test. At revision e461615145d95fbaa34a9fe2a21d23adcf159ebf, GitHub Actions run 38589662993 passed the committed research-plane tests (86 discovered research tests), assurance tests (61), runtime tests (311), hardening tests (12), compile, static acceptance, container build and public Deriv data transport check. The authenticated real-account and transaction lifecycle actions were skipped because production credentials were not configured. A subsequent code update in this PR adds two provenance/mixed-dimension tests, so its new head must pass CI again before merge.

## Remaining requirements

1. Connect a genuine instrument-specific price-to-R adapter only for verified linear products; keep Deriv fixed-payout contracts on payoff/settlement accounting.
2. Supply reproducible entry paths with sufficient intrabar resolution and source/time/data hashes.
3. Extend cost evidence to observed/documented instrument economics and empirical fill/slippage distributions.
4. Add partial exits, time/exposure/opportunity-cost analysis and regime-specific results after deterministic semantics are specified.
5. Run candidate comparisons only after data/cost validation, reserve untouched chronological OOS, control multiple testing and review uncertainty independently.
6. Preserve the canonical live lock until independent strategy, broker, runtime, security, soak and release gates all pass.

Decision: RESEARCH_CONTINUE; no candidate exit is endorsed, no strategy is qualified, and live trading remains blocked.
