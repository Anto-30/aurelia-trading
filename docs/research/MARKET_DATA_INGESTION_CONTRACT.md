# Market-data ingestion contract (research plane)

## Scope

research/labs/market_data_ingestion.py is a strict parser and integrity reporter. It does not authorize strategy qualification, fetch a 24-month dataset, start a backtest, place orders, or modify the canonical release gates.

The parser produces the repository's existing StrategyBar objects from research/labs/deterministic_intraday_strategies.py. That avoids adding an unrelated pandas-only layer9 tree or a second simulator. Data can be integrated with the existing detector after the caller checks IngestionResult.eligible_for_research.

Supported sources:
- Standard CSV OHLC with explicit-offset/UTC timestamps, Unix epoch seconds, or naive local timestamps paired with a caller-supplied IANA source timezone.
- Deriv ticks_history candle responses with the exact requested symbol bound through echo_req.ticks_history.
- Deriv ticks_history tick responses with history.times and history.prices.
- Exported tick JSON rows using epoch/quote, datetime/quote, datetime/price, or timestamp_utc/price records. A list of exported records does not prove its symbol; the audit labels this schema DERIV_TICK_EXPORT_RECORDS_CALLER_SYMBOL_ASSERTED.

This is not a promise to parse literally every possible vendor format. Unsupported or ambiguous input fails explicitly; add a tested adapter for a new source rather than guessing columns.

## Fail-closed integrity behavior

- The source file SHA-256 is recorded. A canonical output hash is recorded when bars are emitted.
- Invalid numeric values, non-positive prices, inconsistent OHLC, malformed rows, duplicate bar timestamps, out-of-order bars/ticks, unbound Deriv API responses, and timezone problems are reported. If any blocking issue exists, the entire dataset is marked QUARANTINED and bars is empty. It does not silently drop or repair the bad row.
- Naive CSV timestamps are not assumed to be UTC. Supply the true source timezone as an IANA identifier. Ambiguous fall-back DST timestamps and nonexistent spring-forward timestamps are rejected unless the CSV supplies an explicit UTC offset.
- Data is not automatically forward-filled, interpolated, deduplicated, or clipped. OHLC high/low are checked; they are never rewritten to make invalid bars appear valid.
- Gaps are reported separately. A gap is not automatically a defect: FX weekends, holidays and instrument-specific market closures must be evaluated against the instrument's trading calendar. A gap report is not proof of uninterrupted market coverage.
- The parser does not impose an arbitrary 100-row minimum. Statistical power, minimum trades per cell and historical window requirements belong to the registered research/qualification gate, not a generic file parser.

## Volume semantics

Deriv ticks_history candle schema documents OHLC and epoch. It does not supply a volume field. Raw ticks contain price observations, not centralized exchange volume. Therefore:
- Missing Deriv candle volume remains None.
- Tick counts from resampling are returned separately in tick_counts_by_bar; they are not written into StrategyBar.volume.
- A CSV volume column is labelled SOURCE_REPORTED_UNVERIFIED; presence is not proof of centralized volume, trade volume, or bid/ask delta.
- Never convert synthetic zero/missing volume to 1.0 to avoid divide-by-zero. Indicators requiring volume must receive separately verified volume provenance or remain disabled.

## Deriv historical retrieval: do not trust a requested range until observed

The current Deriv ticks_history API is no-auth market data. The current docs show a default count of 1,000; the legacy default was 5,000. Send count explicitly. The response should be checked against the request's echo_req, exact symbol, exact requested time window, and observed epoch values. An HTTP/WebSocket success response does not establish that the requested historical boundary was respected.

A safe acquisition client must additionally:
1. use a single WebSocket reader and correlate every request by req_id;
2. request one bounded range at a time and preserve the original request and response hashes;
3. paginate only when the next page makes strict backward progress;
4. detect duplicate/overlapping pages and reject repeated pages or cursor stalls;
5. verify first and last observed epochs against the requested bounds;
6. retain source symbol, granularity, API endpoint/version, page count, request parameters and collection timestamp;
7. rate-limit conservatively and stop on errors rather than returning partial data as a complete window.

A prior AURELIA historical-boundary probe returned current-window data for older requested ranges. That output is not eligible for historical backtesting. This PR does not add or claim a historical fetcher, because the available evidence did not establish a reliable full-range retrieval flow. Public tick transport verification and historical data acquisition are different capabilities.

## How to use the result

    from research.labs.market_data_ingestion import ingest_standard_csv

    result = ingest_standard_csv(
        "data/frxEURUSD_m15.csv",
        symbol="frxEURUSD",
        asset_class="financial",
        granularity_seconds=900,
        source_timezone=None,  # CSV must then contain explicit timezone offsets
    )

    if not result.eligible_for_research:
        raise RuntimeError(f"DATASET_QUARANTINED:{result.audit.issue_codes}")

    # The bars now satisfy the canonical StrategyBar contract.
    # Strategy detectors still require their verified instrument tick-size/config.

Do not pass a quarantined result to a backtest. Do not interpret a successful parse as OOS qualification or live readiness.

## References

- Deriv ticks_history: https://developers.deriv.me/docs/data/ticks-history/
- Deriv current-vs-legacy count-default comparison: https://developers.deriv.com/comparison/ticks-history/
- Deriv tick-history response schema: https://github.com/deriv-com/deriv-api-schemas/blob/master/schemas/ticks_history_response.schema.json