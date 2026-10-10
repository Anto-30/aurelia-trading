# US Session Breakout Historical Pilot — Evidence Report

- Run date: 2026-10-10 UTC
- Repository target: \`Anto-30/aurelia-trading\`
- Research branch: \`research/us-open-session-candidates-2026-10-10\`
- Status: **PRELIMINARY DIAGNOSTIC — NOT QUALIFIED**
- Capital authority: false; live execution: false
- This report supersedes the earlier statement that no historical bars were obtained. The bars were retrieved from the connected Massive futures aggregates API into an ephemeral query workspace. They were not present as a tracked AURELIA dataset.

## 1. Data lineage, coverage and limitations

Source endpoint: Massive futures aggregate bars, \`GET /futures/v1/aggs/{ticker}\`, resolution \`5min\`. Exact queried contract tables and rows:

| Contract | Data request window (UTC date filters) | Rows returned |
|---|---|---:|
| MNQH5 | 2024-12-01 to 2025-03-21 | 20,871 |
| MNQM5 | 2025-03-01 to 2025-06-21 | 21,615 |
| MNQU5 | 2025-06-01 to 2025-09-20 | 21,748 |
| MNQZ5 | 2025-09-01 to 2025-12-20 | 21,642 |
| MNQH6 | 2025-12-01 to 2026-03-21 | 21,221 |
| MNQU6 (August window) | 2026-08-01 to 2026-08-31 | 5,545 |
| MNQU6 (September window) | 2026-09-01 to 2026-09-18 | 3,506 |
| MNQZ6 (partial September window) | 2026-09-01 to 2026-09-30 | 5,687 |
| **Total** | **7 distinct contracts** | **121,835** |

The combined queried records contained 121,835 unique \`ticker + window_start\` keys in the workspace. The observed UTC timestamp span was 2024-12-01 23:00 through 2026-09-30 00:00. These figures describe the retrieved rows, not completeness of the exchange calendar. In particular, **April through July 2026 are missing**, and the 2026 data are discontinuous. Requests for MNQM6 and expanded MNQU6/MNQZ6 windows hit the connected data plan's rate limit. Raw bars were not committed to GitHub, both because the workspace is temporary and because redistributing vendor data requires verified entitlement. A cryptographic hash of the raw dataset was not persisted; provenance is therefore incomplete for any formal qualification.

### Contract roll policy used for this exploratory computation

For each session-end date, the selected contract was the queried contract with the greatest volume on the prior available session; ties were broken by ticker. Duplicate bars were de-duplicated by \`ticker + window_start\`. Roll decisions were made with prior-session volume, not the session being evaluated. Observed transitions included H5→M5 on 2025-03-19, M5→U5 on 2025-06-17, U5→Z5 on 2025-09-17, Z5→H6 on 2025-12-17, and U6→Z6 on 2026-09-16. This is a pilot roll rule, not an exchange-endorsed or fully independently audited continuous-contract history. The lack of MNQM6 and other intervals limits the later roll path.

### Session eligibility

Timestamps were converted to America/New_York from UTC, with the 2025 and 2026 daylight-saving boundaries applied. A session was included only if the data had exactly 60 bars in [04:00, 09:00), 18 bars in [09:30, 11:00), 78 bars in [09:30, 16:00), and six five-minute bars in [09:30, 10:00). Incomplete windows and short sessions were excluded, not filled forward.

| Data period | Calendar dates in observed range | Eligible sessions | Partial/incomplete after range | Incomplete range | No-data/closed dates |
|---|---:|---:|---:|---:|---:|
| 2025 | 312 | 242 | 13 | 3 | 54 |
| 2026 (partial) | 118 | 90 | 6 | 0 | 22 |

The 2026 count is not one continuous sample: 52 eligible dates fall in 2026-01-02 through 2026-03-20, and 38 eligible dates fall in the separate 2026-08 to 2026-09 slice.

## 2. Frozen pilot rules

Only completed five-minute candle-close variants were tested. Intrabar first-cross was **not tested**, because the aggregate OHLC bars do not establish tick-by-tick ordering or executable bid/ask prices.

- **A / US premarket range breakout:** range high/low is the 04:00–09:00 ET window. Use the first five-minute close strictly outside that range, with next five-minute bar open as a reference entry. Entry must be possible before 11:00 ET. One entry per session.
- **A1-like stop variant (close signal only):** one 0.25-point tick beyond the completed breakout bar's low/high, with a geometric 2R target.
- **A2 opposite-boundary variant:** stop at the opposite premarket range boundary, with a geometric 2R target.
- **B / 30-minute opening range:** first 30 minutes [09:30,10:00) determine the high/low. Use the first later five-minute close strictly outside the range; next five-minute open is the reference entry. Opposite boundary is the stop. Test a fixed 10-point target separately from 2R.
- For all configurations, use the first eligible breakout only; no re-entry after any exit. If no signal appears, the session is NO_TRADE. Positions are force-closed by the last 15:55 ET five-minute close in this pilot.
- If a stop and target are touched in the same OHLC bar, their order is unknown. The known-order metrics exclude that trade; a separate stop-first conservative metric treats it as a stop.
- Stop gaps are priced adversely at the first bar open when it has passed the stop. Target touches otherwise use the target price. A time exit uses the 15:55 close.

**Important:** next-bar open is a bar-level reference convention, not a broker-executable fill. The tests do not include a quote/limit-order queue model, bid-ask spread, commissions, exchange/NFA/FCM fees, market impact, latency, adverse selection, or financing. Consequently, the slippage sensitivity below is not full net expectancy.

## 3. Preliminary variant results

Expectancy and drawdown are expressed in initial-risk units \(R\). The “stop-first PF” is based on conservative stop-first handling for an OHLC bar that touches both stop and target. “1-tick/side expectancy” subtracts a hypothetical one tick of slippage at entry and exit (two ticks/0.50 index points round trip for MNQ). No actual bid/ask slippage distribution was observed. Results are not adjusted for commissions or spreads.

### 2025 historical development sample — 242 eligible sessions

| Variant | Trades | No-trade sessions | Win rate (stop-first) | Avg win (R) | Avg loss (R) | Expectancy / trade (R) | PF stop-first | Expectancy with 1 tick/side slippage (R) | PF with slippage only | Max DD (R) | Longest losing streak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A breakout-candle stop, 2R | 220 | 22 | 31.4% | 1.96 | -0.98 | -0.0604 | 0.911 | -0.0734 | 0.893 | 27.18 | 10 |
| A opposite-range stop, 2R | 220 | 22 | 47.7% | 1.03 | -0.83 | 0.0576 | 1.132 | 0.0536 | 1.123 | 20.11 | 6 |
| B opposite-range stop, 2R | 186 | 56 | 52.2% | 0.80 | -0.80 | 0.0355 | 1.093 | 0.0316 | 1.082 | 9.80 | 4 |
| B opposite-range stop, fixed 10 points | 186 | 56 | 94.1% | 0.077 | -0.934 | 0.0175 | 1.316 | 0.0136 | 1.245 | 2.63 | 2 |

The 2025 A breakout-candle-stop sample had three same-bar stop/target ambiguities; the stop-first metric counts them conservatively as losses. The 2R arithmetic is based on planned price risk from the next-bar reference entry; it is not a net-money 2R guarantee.

### 2026 Q1 historical diagnostic — 52 eligible sessions

This segment follows the 2025 development window chronologically, but the hypotheses were not sealed in a preregistered campaign before seeing this data. It is **not** qualified untouched OOS evidence.

| Variant | Trades | No-trade sessions | Win rate | Expectancy / trade (R), stop-first | PF stop-first | 1-tick/side expectancy (R) | PF with slippage only | Max DD (R) | Longest losing streak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A breakout-candle stop, 2R | 49 | 3 | 42.9% | 0.2180 | 1.392 | 0.2101 | 1.375 | 6.17 | 5 |
| A opposite-range stop, 2R | 49 | 3 | 53.1% | 0.1811 | 1.533 | 0.1782 | 1.522 | 3.96 | 3 |
| B opposite-range stop, 2R | 46 | 6 | 58.7% | 0.0799 | 1.287 | 0.0771 | 1.276 | 2.54 | 4 |
| B opposite-range stop, fixed 10 points | 46 | 6 | 91.3% | -0.0372 | 0.572 | -0.0400 | 0.542 | 2.25 | 1 |

### August–September 2026 disconnected diagnostic — 38 eligible sessions

This is a separate segment after a major source-data gap, not a continuous OOS campaign.

| Variant | Trades | No-trade sessions | Win rate | Expectancy / trade (R), stop-first | PF stop-first | 1-tick/side expectancy (R) | PF with slippage only | Max DD (R) | Longest losing streak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A breakout-candle stop, 2R | 30 | 8 | 30.0% | -0.1914 | 0.727 | -0.2002 | 0.717 | 10.91 | 6 |
| A opposite-range stop, 2R | 30 | 8 | 50.0% | 0.1006 | 1.371 | 0.0979 | 1.359 | 3.31 | 3 |
| B opposite-range stop, 2R | 28 | 10 | 42.9% | -0.0513 | 0.852 | -0.0542 | 0.845 | 6.52 | 4 |
| B opposite-range stop, fixed 10 points | 28 | 10 | 92.9% | 0.0048 | 1.097 | 0.0019 | 1.039 | 1.22 | 1 |

The fixed 10-point B target exhibits high win rate but very small mean win; it is negative in the Q1 diagnostic and almost break-even in the disconnected Aug/Sep slice even before spread/commissions. The breakout-candle-stop A variant is negative in 2025 and Aug/Sep, with a materially different Q1 result. This instability is an explicit reason not to promote either rule.

## 4. Interpretation and decision

1. **No candidate is qualified.** The results are preliminary descriptive statistics with limited windows and multiple variants. They are not evidence of a robust, statistically significant or executable edge.
2. **A breakout-candle-stop 2R is rejected from advancement at this stage** because expectancy/PF deteriorates outside the Q1 segment.
3. **A opposite-boundary 2R merits further research only**, not production. Its preliminary expectancy is positive in these segments but sample selection was not preregistered, source coverage is incomplete, and costs are materially under-specified.
4. **B 2R is regime-sensitive**: mildly positive in 2025/Q1 and negative in Aug/Sep.
5. **B fixed-10 is rejected from advancement**: a superficially high win rate is not enough when average win is small, Q1 expectancy is negative, and costs erode the disconnected sample to roughly zero.
6. Do not present the “slippage-only” figures as after-cost profitability. Missing spread, real fills and commission means true net expectancy is **UNDETERMINED**.
7. The data provider response did not include bid/ask/time-sequenced trades, so intrabar first-cross and true stop/target ordering remain NOT_TESTED. Candidate C session reversal and Candidate D multi-timeframe pivot filter remain specifications only.
8. Results in index points/R are not portable to Deriv R_100, NQ, CFDs or other symbols. MNQ itself cannot meet a $1 loss budget: CME defines MNQ as $2 per Nasdaq-100 index point with a 0.25-point tick ($0.50/tick), so even a one-point stop is $2 per contract before costs. Current account balance/margin and risk capacity must be independently verified; this pilot does not authorize such a trade.

## 5. Next experiment before any re-run

- Obtain a redistributable/authorized, continuous minute or finer quote/trade dataset for MNQ with complete April–July 2026 coverage, and save dataset SHA-256, request parameters, retrieval date and license/entitlement record.
- Pre-register A1/A2/B variants and reserve an untouched prospective holdout. Do not retune using the reported 2026 segments.
- Obtain realistic broker/exchange commissions, bid/ask spreads, slippage/latency distributions and fill assumptions; run sensitivity across 1, 2 and 4 ticks each side plus spread/fee scenarios.
- Re-run using event-level/tick data to disambiguate stop/target ordering; compare against no-trade and a base reference model; report uncertainty intervals, serial-dependence-aware bootstrap, parameter-search count, symbol/regime segmentation and daily net P&L including zero-trade sessions.
- Keep all four candidates RESEARCH_ONLY until a separate sealed evaluation, calibration, paper/shadow process, and the current AURELIA deterministic release process are complete. This report does not modify the strategy registry, Risk Warden, Execution Firewall, LIVE_LOCK or deployment.
