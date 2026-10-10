# AURELIA US-Session Strategy Candidates — Research Contract

**As-of repository inspection:** 2026-10-10  
**Canonical source inspected:** Anto-30/aurelia-trading, main at cd858bec8fb5eb05dfc32733a6062bf2e9c95ae9  
**Lifecycle:** RESEARCH_ONLY / NOT_TESTED  
**Capital authority:** false  
**Live execution:** false

## 1. Decision and scope

This document turns four session/multitimeframe ideas into separable hypotheses. The initial A/B specifications and signal primitives were committed before the historical pilot was calculated. The repository itself contains no stored historical Nasdaq futures dataset. A subsequent exploratory pilot used temporary third-party MNQ 5-minute aggregates retrieved on 2026-10-10; the data were not persisted or cryptographically hash-pinned, full broker costs are absent, and parts of 2026 are missing. Preliminary results are documented in [the pilot report](../reports/research/US_SESSION_BREAKOUT_PILOT_2026-10-10.md). These results do not establish profitability or qualification.

Two signal-construction primitives have been added in research/labs/session_breakout_candidates.py. They emit research-only candidates and reference price levels. They are not a complete backtester, an execution adapter, or a strategy registry. A next-bar open or next tick bid/ask used by these primitives is an explicit reference-price convention, not proof of a broker fill.

## 2. Current AURELIA state relevant to this mandate

### Repository and research infrastructure inspected

- Canonical source is main; current branch identity must be resolved at the start of each task.
- Research package: research/; current research experiments include hourly intraday-bias measurement and a prospective Deriv R_100 tick experiment.
- Prospective Deriv research: research/r100_prospective_oos_collector.py; the workflow .github/workflows/r100-prospective-oos.yml collects public R_100 observations on a scheduled basis and stores campaign state as an Actions artifact.
- Research checks: research/labs/tests/test_intraday_bias_measurement.py and research/labs/tests/test_r100_prospective_oos_collector.py.
- Evidence controls include assurance/research_quality.py, runtime/validation/walk_forward.py and research/ml/schema.py. Future-dated features are rejected by the ML evidence contract.
- Current strategy lifecycle is defined in runtime/strategy/governance.py: EXPERIMENTAL -> REPLAYABLE -> VALIDATED -> CALIBRATED -> SHADOW -> CANARY -> PRODUCTION; SUSPENDED is a terminal/hold state for promotion. The code in that module requires evidence identifiers and an approver but does not itself inspect the semantic validity of every evidence artifact. The wider certification and capital-release controls remain required.
- runtime/strategy/__init__.py explicitly says strategy governance lives there, not strategy implementations. This inspection did not find a single central registry file containing all names mentioned by the owner (S7, S6, S3, CRT and MICRO_SCALP_R100_TICK_MOM). This change intentionally does not create a replacement registry or overwrite those strategies. A local/runtime inventory is still needed before any integration.
- The tracked data/runtime files are readiness/access-state snapshots, not OHLCV price history. No historical CME Nasdaq futures bars were found in the inspected main tree. Temporary research access later retrieved 121,835 unique MNQ 5-minute aggregate rows across seven quarterly contracts; this was not committed, source hashes were not preserved, and April–July 2026 is missing. That dataset supports only the explicitly preliminary diagnostic report, not a sealed qualification evidence set.

Historical readiness snapshots are not current broker evidence. The newest verified CI runs can be used to establish that tests executed, not to substitute for market, broker, deployment, or strategy qualification evidence.

## 3. Instrument compatibility decision

### Track US futures separately

The intended instrument for candidates A and B is not yet authorized/configured. If the hypothesis is about the US cash opening range while trading Nasdaq futures, use a named CME Globex contract with a versioned roll policy, a licensed/authorized CME price feed, timestamp semantics, bid/ask or trade data, and broker-specific margin/commission/slippage inputs. Do not substitute index CFD prices, cash-index prints, or Deriv Synthetic Indices.

CME's published specs state that MNQ is $2 per index point with a 0.25-point minimum tick (about $0.50 per tick per contract). NQ is $20 per point with a 0.25-point minimum tick (about $5 per tick per contract). E-nano Nasdaq-100 (NNQ) is listed separately at $0.20 per point and a 0.50-point tick in CME's product comparison. The exact contract, expiry, roll adjustment, data entitlement, and broker terms must be pinned before testing.

A 10-point target therefore does not mean a 10-dollar result: before costs, it corresponds to about $200 per NQ contract, $20 per MNQ contract and $2 per NNQ contract. A one-point loss on one MNQ is $2 before costs. The futures sizing model, exchange/FCM margin and loss budget make these contracts incompatible with a $1 cash balance; the risk engine must reject such an order rather than resize assumptions to fit.

### Keep Deriv Synthetic Indices separate

The current AURELIA research collector targets Deriv R_100 using public tick history. That is not NQ or MNQ. Deriv describes its Synthetic Indices as independently generated, available 24/7 and not driven by ordinary real-market sessions or news events. Therefore a New York cash-open, London-liquidity or US-macro premise must not be transferred to R_100 without a new independent hypothesis and R_100-specific validation.

For any Deriv contract, query current active_symbols/contracts_for and proposal economics through the documented API. Use the actual account currency and contract payout/stake definition. A stop distance in index points is not interchangeable with a binary/options stake or payout. No $1 trade is eligible unless the current account balance, exact contract quote, allowed loss, and execution minimum all pass AURELIA's existing deterministic risk controls.

### Source references

- CME Micro E-mini Nasdaq-100 specifications: https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.contractSpecs.html
- CME E-nano Nasdaq-100 comparison: https://www.cmegroup.com/markets/equities/nasdaq/e-nano-nasdaq-100.quotes.html
- Deriv historical ticks API: https://developers.deriv.com/docs/data/ticks-history/
- Deriv market-data and symbol endpoints: https://developers.deriv.com/docs/data/
- Deriv trading proposal and buy lifecycle: https://developers.deriv.com/docs/trading/
- Deriv Synthetic Index market description: https://deriv.com/newsroom/updates/deriv-derived-indices-on-tradingview

## 4. Candidate A — US pre-cash-open range breakout

### Candidate identity

- ID: US_PREMARKET_RANGE_BREAKOUT
- Market/timezone: target must be a specific CME Nasdaq contract or a separately specified CFD; America/New_York is the authoritative session zone.
- Range timeframe: five-minute candles, timestamped by bar-open time.
- Range: candle starts from 04:00:00 inclusive through 08:55:00 inclusive ET, equivalent to the half-open interval [04:00, 09:00). Require exactly 60 consecutive completed five-minute candles. Range high is the maximum eligible high; range low is the minimum eligible low. A missing, duplicate, unaligned or stale bar invalidates the session.
- Entry eligibility: signal entry must occur at or after 09:30 ET and strictly before 11:00 ET. The first qualifying direction wins; no second entry after stop, target, reversal or exit. If nothing qualifies, record NO_TRADE.
- Position management: force-flat by 16:00 ET as a frozen initial research default; do not carry positions overnight. This cutoff is a protocol choice to test, not a claim of advantage.
- Long/short levels: long only above the range high; short only below the range low. Equality is not a breakout. All timestamps are stored in UTC and mapped to New York time using IANA timezone data, so daylight-saving changes are not hard-coded.

### Separate entry variants

**A1 — intrabar first-cross.** Requires chronologically ordered, sufficiently granular price observations plus synchronized bid/ask quotes. The first observed price strictly above the high creates a long signal; the first observed price strictly below the low creates a short signal. Enter using the next quote available after the signal: ask for long, bid for short. Same-tick fills are not assumed. If timestamp/sequence ordering cannot resolve the order of events, classify the candidate as ambiguous and exclude it from decisive performance statistics.

Intrabar stop variants: (i) the opposite range boundary; (ii) the observed breakout-candle extreme accumulated only up to the signal timestamp, with one instrument tick of buffer. Do not use the final high/low of a still-open breakout candle at signal time: that would use future information.

**A2 — completed five-minute close.** The first completed five-minute candle close strictly above/below a range boundary confirms a long/short. Entry reference is the open of the immediately following five-minute bar, which is only a bar-level proxy and must be replaced or stress-tested with executable bid/ask + slippage assumptions in the backtest. A missing next bar makes that session NO_TRADE/data-incomplete; do not silently skip to a later signal.

A2 stop variants are independent configurations: (i) one tick beyond the completed signal candle low/high; (ii) opposite range boundary. Do not mix the stop rules in a single statistic.

### Targets and R

Evaluate a two-R geometric target as one variant. Define planned price-risk as the distance between reference entry and stop, but calculate monetary risk using contract multiplier, quantity, stop/entry costs, commission and realistic slippage. Report gross-price 2R and net-cost-adjusted 2R separately. For net-cost 2R, the modeled net target P&L must equal twice the modeled initial loss at the stop; do not label an unadjusted target as net 2R.

If both stop and target are touched inside a candle, replay lower-level data to establish event order. Without such data, mark the outcome ambiguous rather than choosing the favorable path.

## 5. Candidate B — 30-minute opening-range breakout

### Frozen initial candidate

- ID: US_OPENING_RANGE_30M_BREAKOUT
- Range: first two completed 15-minute candles after the US cash open, starting 09:30 and 09:45 ET. Their high/low establish the range, finalized at 10:00 ET. Missing either candle invalidates that session.
- Confirmation: first subsequent completed five-minute candle close strictly above/below the range, at or after 10:00 ET. This five-minute confirmation is a frozen initial choice because the transcript does not specify a post-range confirmation timeframe.
- Entry: next five-minute bar open as a research reference price, then executable-price modeling from eligible bid/ask data.
- Stop: opposite range boundary only.
- Entry cutoff: strictly before 11:00 ET as the initial research default; one entry per session; no entry if confirmation is absent. Force-flat by 16:00 ET as the initial research default.
- Target variants must remain separate: B1 fixed 10 index points; B2 geometric 2R; B3 cost-adjusted net 2R. A fixed 10 points has different dollar risk/reward and practical meaning for NQ, MNQ, NNQ and CFDs; never share performance conclusions across them.
- No retaking a trade after a stop or reversal. Record the first valid direction and exit outcome only.

The new module in research/labs/session_breakout_candidates.py implements range and signal/reference-price construction for A2 and the initial B configuration. It intentionally does not claim fills, simulate exits, apply commissions or qualify a strategy.

## 6. Candidate C — session reversal and subsequent expansion

**Hypothesis, not an established edge:** a liquidity sweep and reversal during one defined futures session predicts a larger directional move during the immediately following session.

Freeze this initial operationalization before seeing candidate results:

- Target only a specifically named CME futures contract, not R_100. Define three New York time blocks: overnight 18:00 on the prior calendar day to 02:00; Europe/pre-cash 02:00 to 09:30; US day 09:30 to 17:00. Respect the daily exchange maintenance interval and actual exchange calendar. Session labels are research buckets, not proof of liquidity or causation.
- Reference levels are the completed high/low of the immediately preceding defined session.
- Reversal signal: the first completed five-minute candle that trades at least one tick beyond a previous-session high and then closes back below that previous high is a short candidate; a one-tick sweep below the previous-session low followed by a close back above it is a long candidate. One signal maximum per session. If both boundaries are swept and granular order cannot be established, mark ambiguous.
- Entry for the directional trade hypothesis is the next session's first executable quote, only if the planned stop has not already been crossed. Stop is one tick beyond the sweep-session extreme; no valid positive risk distance means NO_TRADE. Evaluate 1R and 2R target variants independently and force-flat at the end of the following session.
- Descriptive expansion outcome: compare the following session's high-low range with the median high-low range of the previous 20 completed sessions of the same time-block type. Calculate separately from trade P&L. Directional adverse/favourable excursion, stop/target hits, and next-session range expansion are separate outcome variables.
- Controls: unconditional next-session range baseline, random/session-label permutation tests that respect serial dependence, and no-trade baseline. Use a locked chronological holdout and correction for all session/sweep/target variants tried. Any result is symbol/regime-specific.

No implementation or backtest result for C is claimed in this change; only the research protocol is specified. Its session windows and signal definitions must be frozen in a versioned campaign manifest before accessing evaluation results.

## 7. Candidate D — multi-timeframe market structure

**Hypothesis:** confirmed higher-timeframe structure improves the performance or risk profile of an otherwise unchanged lower-timeframe entry. It is a contextual filter, not a discretionary entry signal by itself.

- Calculate separate bars for monthly, weekly, daily, four-hour and one-hour timeframes using venue-appropriate calendars and completed bars only.
- Initial pivot rule: a swing high at bar i is a strict high greater than each of the two bars before and two bars after it; a swing low is a strict low less than the corresponding four lows. Equal extrema are not pivots in v0.1. The pivot becomes available only after the second right-side bar has fully closed. Its usable timestamp is the confirmation close, not the pivot candle timestamp.
- Structure is bullish only when the latest two confirmed swing highs are rising and the latest two confirmed swing lows are rising; bearish only when both sequences are falling; otherwise classify as mixed/undefined. Trendlines may connect only two already-confirmed same-type pivots. Normalize distance and slope by a trailing ATR calculated only from information available at the decision time.
- A monthly/weekly/daily/4h/1h cascade may be used as a pre-registered filter variant. At each decision timestamp, all features must have an availability timestamp no later than that decision.
- Test filter value through ablation: base entry system versus identical entries plus structure filter, with identical dates, exit rules, costs and risk model. Report coverage/accepted signal count, trade expectancy, tail loss, drawdown and uncertainty. If trade count or net expectancy deteriorates, do not make this filter mandatory.

No structure-filter implementation or evidence is claimed in this change. A separate tested feature builder would need causal resampling, pivot-confirmation tests and data-leakage tests before it could be added to a strategy.

## 8. Contradiction and ambiguity register

| ID | Original ambiguity or conflict | Frozen handling |
|---|---|---|
| C-01 | “Premarket” can be mistaken for the futures exchange's full trading session. | Label Candidate A as US pre-cash-open range breakout; use named instrument and clock window. |
| C-02 | Instrument not specified: NQ/MNQ futures, CFD and Deriv R_100 are not equivalent. | Separate configs, feeds, data hashes, costs and promotion decisions. Current active research target R_100 does not imply the new US-session candidate targets R_100. |
| C-03 | 04:00-09:00 boundary semantics are unclear. | Use bar-open timestamps and half-open interval [04:00, 09:00); exactly 60 five-minute bars. |
| C-04 | Daylight-saving time changes shift UTC. | Store UTC; derive session windows with America/New_York; test both sides of DST. |
| C-05 | Intrabar high/low touches can occur in unknown order in OHLC data. | Use ordered ticks for A1; otherwise mark ambiguous. |
| C-06 | Full breakout-candle extremes are unknown at an intrabar entry. | Prohibit that stop for A1; use opposite boundary or observed-to-date extreme; reserve final candle-extreme stop for a post-close variant. |
| C-07 | A five-minute close signal cannot be filled at a price known before that close. | Use a next-bar open only as a reference-price convention and model executable bid/ask, gaps and costs. |
| C-08 | “2R” can mean price-distance multiple or net monetary reward multiple. | Report gross geometric 2R and cost-adjusted net 2R as separate versions. |
| C-09 | Candidate B's post-range confirmation candle/timeframe is not stated. | Freeze five-minute close confirmation after 10:00; this is a test choice, not a proven optimal rule. |
| C-10 | Fixed 10-point target is instrument dependent. | Test separately with multiplier/tick/fees and never compare points as though they were dollars. |
| C-11 | One trade/session, one trade/day and reversal re-entry can conflict. | One first eligible signal per defined session per candidate; no second entry after any exit. |
| C-12 | Force-flat rule is unspecified. | Initial test convention: exit by 16:00 ET for A/B and end of next session for C; version and sensitivity-test it. |
| C-13 | C's asserted session reversal/expansion relation is not specified or proven. | Use one defined sweep/re-entry rule, explicit following-session entry/outcome, baselines and chronological holdout. |
| C-14 | Multi-timeframe pivots/trendlines can be plotted retrospectively. | Make pivots available only after two subsequent bars close; use only confirmed pivots. |
| C-15 | A daily dollar target can encourage forced trades or risk escalation. | $250/day is aspirational only; no quota, martingale, loss chasing or risk-limit relaxation. |
| C-16 | A valid signal or probability score may be uncalibrated. | Apply AURELIA's existing 0.55-0.75 probability policy with no clipping; unknown/stale/uncalibrated/drifted is NO_TRADE. |
| C-17 | A green unit/CI test could be confused with qualification. | Separate code-test PASS from strategy OOS, calibration, execution economics, broker, runtime and release-gate evidence. |

## 9. Reproducible research protocol

Before each campaign, create a frozen manifest with unique hypothesis and version identifiers, symbol/contract, price source and entitlement, timestamp/bar convention, dataset hashes, date window, timezone and session, source commit, configuration hash, parameter search space, trial count, random seeds, entry/stop/target configuration, cost model and selection rule. Freeze the untouched OOS interval before evaluating variants; record every experiment including rejected variants.

Data checks: duplicate/order/gap detection; source timezone and DST conversion; adjustment/roll policy; OHLC validity; session completeness; outliers; source age; missing bid/ask; contract expiry; quote timestamp/sequence integrity; and alignment between tick and bar feed. A failed check invalidates the affected session rather than being silently repaired.

Evaluation protocol:
1. Chronological development / validation / sealed prospective OOS splits. No retuning after OOS access. The current repo's R_100 methodology demands no OOS reuse and includes multiple-testing controls; preserve that principle.
2. Walk-forward by time and separate results by instrument, regime, long/short side, session, stop mode, target mode and volatility bucket.
3. Compare to no-trade and a simple base breakout without the optional filter. Count all trials and adjust for multiplicity. Use block bootstrap or other dependence-aware uncertainty estimation for serially correlated intraday observations.
4. Use tick/event replay where stop/target ordering matters. Missing lower-level ordering = ambiguous trade, never a favorable assumed fill.
5. Cost model requires source-specific spread, slippage distribution, entry/exit commission, tick/point value, contract quantity, exchange/FCM fees and financing where relevant. Missing cost inputs mean net expectancy is UNDETERMINED.
6. For each variant report sessions eligible, sessions rejected/incomplete, trades and no-trade sessions; wins/losses/flat; win rate; mean/median win and loss; realized reward/risk; gross/net expectancy in R and currency; profit factor after costs; max drawdown; longest losing streak; recovery time; daily P&L distribution including zero-trade days; long/short; regime; slippage/spread sensitivity; OOS confidence intervals; parameter stability; trial count; and selection-bias risk.

The minimum sample threshold is governed by existing AURELIA qualification requirements (the continuous research policy calls for 100+ OOS observations/trades per Strategy x Symbol x Regime where applicable). This is a floor, not proof of sufficient statistical power. Campaign length should be determined by power/precision and available independent regimes, not by choosing a sample size that happens to pass.

## 10. Integration and controls

These candidates remain research-plane only. Do not add them to live production strategy execution or overwrite existing S7, S6, S3, CRT or scalping definitions.

Required path if later validated: research manifest -> tested implementation -> independent code/data review -> replayable evidence -> chronological/OOS qualification -> calibration/drift -> net economics -> shadow/paper -> existing strategy-governance transitions -> existing broker/runtime certification -> explicit deterministic release authority.

Regression tests must cover both DST transitions, timestamp awareness, exact range-bar counts, gap/duplicate rejection, strict comparisons, first-signal-only behavior, no-trade cases, cutoff, next-quote execution convention, stop variants, 2R variants, fixed-target variant, adverse gaps, crossed/invalid quotes, ambiguous exit events, future-feature rejection, and preservation of LIVE_LOCK/account isolation/risk/firewall/idempotency/reconciliation/kill-switch invariants.

## 11. Evidence-backed status matrix

| Deliverable or gate | Status | Evidence / missing item |
|---|---|---|
| Current canonical branch/source inspected | PASS | main tree SHA cd858bec8fb5eb05dfc32733a6062bf2e9c95ae9; live gate remains config/LIVE_LOCK.yaml |
| Existing research/test/validation architecture inspected | PASS | paths listed in Section 2 |
| Candidate A/B initial research primitives and tests authored | IMPLEMENTED_ON_RESEARCH_BRANCH | research/labs/session_breakout_candidates.py and research/labs/tests/test_session_breakout_candidates.py; still requires CI execution and review |
| A/B unambiguous versioned specs | SPECIFIED | Sections 4-5 |
| Candidate C/D hypotheses | SPECIFIED_NOT_IMPLEMENTED / NOT_TESTED | Sections 6-7; no result metrics claimed |
| Authorized CME historical data source and exact contract | PARTIAL / BLOCKED FOR QUALIFICATION | A connected Massive endpoint returned MNQ 5-minute futures aggregates; licensed reuse entitlement is unverified, the raw data were not persisted/hash-pinned, and the timeline has a major gap |
| Historical Nasdaq OHLCV data available in repo | NOT_FOUND IN REPO; TEMPORARY EXTERNAL DATA RETRIEVED | 121,835 unique rows from seven MNQ quarterly contracts were queried into an ephemeral workspace; source hash and complete continuity not established |
| A/B historical aggregate-bar pilot | PRELIMINARY DIAGNOSTIC; NOT QUALIFIED | Reported in reports/research/US_SESSION_BREAKOUT_PILOT_2026-10-10.md. Variants were compared across 242 sessions in 2025, 52 Q1 2026 dates and a disconnected 38-session Aug/Sep slice. No sealed OOS, reliable confidence estimates, full costs, or tick-level execution proof |
| R_100 candidate compatible with US session logic | NOT_ESTABLISHED | Requires separate R_100-specific hypothesis/validation; no transferred stats |
| Mapping of named existing strategies to current runtime registry | BLOCKED | No central registry containing all owner-named IDs found in inspected tree; local/runtime inventory needed before integration |
| Strategy lifecycle/governance | INSPECTED | runtime/strategy/governance.py has stricter existing stage names |
| Broker account/balance, production runtime and transaction certification | BLOCKED | separate existing certification requirements; not supplied by research branch |
| Live execution authorization | BLOCKED | LIVE_LOCK remains authoritative and non-live; no release control changed |

## 12. Ranked remaining blockers and owners

1. **Instrument/data contract — owner: research lead + data/feed owner.** Decide CME MNQ/NQ/NNQ versus a specific CFD; confirm license/entitlement, front/roll policy, historical bid/ask/ticks, contract/calendar, tick value, broker commissions/margin and time semantics.
2. **Executable research harness and cost model — owner: Claude Code / engineering runtime.** Extend/reuse the current research tooling (do not add a competing capital system); implement stop/target replay, daily aggregation, missing-data/ambiguity handling and reproducible metrics. The new primitives are not a complete backtester.
3. **Independent hypotheses and statistical review — owner: Grok/JEV/Kimi-style reviewers when actually connected.** Challenge session definitions, survivorship/roll bias, multiple testing, costs, causal timing and OOS reuse. A task/configuration assignment is not execution proof; require attributable result evidence.
4. **C/D implementation — owner: research engineering.** Implement session block builder and pivot-confirmation feature builder only after the data/market selection is frozen; add unit and leakage tests.
5. **Historical and prospective evaluation — owner: quantitative research.** Run A1/A2 and B1/B2/B3 as separate campaigns, then C and D; report NO_TRADE sessions, all variants tried, dependence-aware confidence, OOS and cost sensitivity. Do not publish fabricated statistics.
6. **Existing-strategy mapping and review — owner: Claude Code + AURELIA governance.** Inspect local runtime/agent registry and map S7/S6/S3/CRT/scalping before any registry integration. Preserve all previous definitions and only make a reviewed PR if qualification supports a change.
7. **Live-release requirements — owner: AURELIA deterministic release authority / operations.** Independently complete authenticated Deriv identity and fresh balance, stake affordability, qualified strategy, current runtime health, broker-confirmed transaction lifecycle, ledger reconciliation, required soak and explicit release authorization. Research results do not satisfy these operational gates.

No real-money orders, production deployments, secret access, LIVE_LOCK changes, or production strategy promotions are authorized by this candidate research mandate.
