# Pre-FOMC Event Study — Research Protocol

**Status:** Research-only; historical edge is not validated for AURELIA.  
**Capital authority:** None. **Live execution:** Forbidden.  
**As-of:** 2026-10-28.

## Research question

Does the equity index exhibit a positive return from the previous US equity session's reference timestamp through 15 minutes before a scheduled FOMC policy statement, after adjustment for realistic implementation costs? Does any effect survive later samples, alternative windows, non-FOMC controls, and out-of-sample testing?

This protocol separates (a) an academic event-study replication from (b) a tradable strategy test. A positive event-study mean does not, by itself, establish a net executable edge.

## Primary literature and what it does—and does not—establish

1. **Lucca and Moench (2015), Journal of Finance 70(1), 329–371.** The study documents large pre-announcement US equity returns in its 1994–March 2011 sample. The New York Fed Staff Report 512 landing page and linked PDF contain the original design and limitations: https://www.newyorkfed.org/research/staff_reports/sr512.html
2. **Kurov, Wolfe and Gilbert (2021), Finance Research Letters 40, 101781, DOI 10.1016/j.frl.2020.101781.** Their extended sample ends in December 2019 and reports that the drift essentially disappeared after 2015. Their published summary table reports an average of 0.492% for the September 1994–March 2011 sample (131 observations) versus 0.047% for April 2011–December 2019 (70 observations). The later average is small relative to its reported standard error; these are sample statistics, not a forecast. https://doi.org/10.1016/j.frl.2020.101781
3. **Ignatieva and Ohashi (2025), Applied Economics 57(17), 2021–2037, DOI 10.1080/00036846.2024.2322573.** Their study of FOMC press-conference events reports positive pre-announcement equity returns but says the effect becomes insignificant shortly after disclosure. This is evidence for a time-localized phenomenon, not proof that a simple entry/exit rule is robust after costs. Abstract: https://ideas.repec.org/a/taf/applec/v57y2025i17p2021-2037.html
4. **OHLCV.io (2026, non-peer-reviewed research note).** A recent, differently specified E-mini S&P futures window reports a possible return of the drift in the 2021–2026 period, but a t-statistic of 1.72 and 46 events. Its own discussion cautions that the result may be noise. Because its window and data/analysis are not identical to the canonical study, this is a hypothesis to test independently, not a replication: https://ohlcv.io/posts/more-history-may-not-be-more-evidence/

**Synthesis:** The evidence is mixed across eras and event definitions. Keep the thesis open for falsifiable research; do not treat the historic headline return as a current expected return.

## Event timing rule

- Each row in the event calendar must contain `meeting_date` and the **actual scheduled statement timestamp** in `announcement_at`, with an explicit timezone/offset or an unambiguous New York local time.
- The reference timestamp is exactly 15 minutes before that event's announcement timestamp.
- Use the same local clock time on the preceding verified US equity trading session for entry.
- The historic scheduled statement time was commonly 14:15 ET, giving a 14:00 ET reference time. The post-2013 convention is 14:00 ET, giving a 13:45 ET reference time. Do not hardcode one reference time across all years.
- Missing statement timestamps must be excluded and reported. Do not infer the time only from the meeting date.
- The script uses exact reference-minute samples; it does not interpolate a missing price.

## Data policy and timestamp normalization

### Preferred replication data
Use a timestamped S&P 500 index futures series that covers the relevant sample: S&P 500 futures for the pre-ES period and E-mini S&P 500 futures after ES trading began. Respect the vendor's licence and contract-roll conventions. Do not substitute Deriv synthetic indices.

### Secondary proxy
SPY one-minute bars can be used for a **separately labelled proxy study**, not as an exact reproduction of the futures paper. The IEX-only feed is not the consolidated US equity tape and can contain missing minutes. The current connector's historical request returned no 2011 bars and only partial access to later dates, so a complete SPY study was not produced in this run.

### Bar-time conventions
Normalize each data source before running the study. Many one-minute OHLCV feeds label a bar by its **start** time while `close` is observed at the end of that minute. Pairing the start label with the close price creates a one-minute timing mismatch. Shift the timestamp to the price observation time or use a suitable timestamp-aligned observation. Record the source, feed, timezone, timestamp convention, adjustment convention, extraction time, and SHA-256 hashes in the run manifest.

### Official event source
Use the Federal Reserve's FOMC calendars for meeting dates, then independently validate each announcement's timestamp using the associated statement/event record or an authoritative historical release record: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

## Prespecified analysis

1. **Replication:** implement the published event window and return convention; reconcile observation counts against the published sample before interpreting differences.
2. **Recent sample:** separately evaluate post-2020 data through the latest fully completed scheduled FOMC announcement. Do not include a same-day event until its timestamp and price window are complete.
3. **Controls:** compare with matched non-FOMC sessions using the same clock window; report differences in mean and median returns and the full event-level ledger.
4. **Returns:** report both simple returns and log returns. Apply assumed round-trip costs additively in log-return space, but clearly label this as a haircut—not a historical fill simulation.
5. **Costs:** run at least 0, 2, 5, and 10 bps as transparent sensitivity scenarios until instrument-specific bid/ask, fees, slippage, and execution data are verified. Do not choose a cost only because the strategy remains profitable.
6. **Inference:** disclose valid/excluded observations, mean, median, standard deviation, win rate, profit factor, compounded return, drawdown, and confidence intervals. A descriptive t-statistic is not a validated p-value. Use an inference method appropriate to a small event sample and dependence; account for testing multiple windows/variants.
7. **Out of sample:** lock a primary specification before examining the final holdout. Report pre-2011 replication, 2011–2019, 2020–2026, and any later sealed holdout separately. Do not optimize parameters on the holdout.
8. **Robustness:** test announcement-time variants only when supported by actual event metadata; report the primary result even if alternatives look better. Check data gaps, DST, holidays, timestamp alignment, split/dividend adjustment, repeated/special meetings, and event exclusions.

## Data-access and execution evidence for this run

- A read-only Alpaca market-data check returned 0 SPY minute bars for a September 2011 request, so it cannot support the original-sample replication from this source.
- Spot checks for several later FOMC windows returned values through the IEX feed, but repeated requests subsequently returned internal errors. The spot checks were incomplete and were not used to publish cohort performance metrics.
- The HF Data Library describes a free one-minute US equity dataset under CC BY 4.0, but programmatic full-history downloads require a free account/API key and profile verification. This run did not register an account or use/guess credentials. Its post-March 2022 bars are identified as IEX-sourced. Start here: https://hfdatalibrary.com/ and API notes: https://hfdatalibrary.com/pages/api
- No complete, hash-pinned research dataset and no validated complete event file were available in this run. Therefore **no full historical backtest result is claimed**.

## AURELIA release gate

This research module may write research CSV/JSON outputs only. It must never generate orders, modify capital-plane state, change `config/LIVE_LOCK.yaml`, or grant capital authority. A successful research test or positive backtest does not change the live-release decision. Require data provenance, independent methodology review, independent code review, completed CI, sealed out-of-sample evidence, and human approval before any future readiness review. Until then, posture remains `RESEARCH_ONLY` and `VERIFY_ONLY`.
