# Research Data Validation Gate v0.1.0

**Status:** Engineering utility; research-only; not a strategy specification.

## Scope

This gate validates timestamped OHLC datasets before research. It does not infer strategy rules, repair prices, forward-fill gaps, select instruments, calculate trading costs, or authorize capital.

## Fail-closed requirements

- Require open, high, low and close columns.
- Require a non-empty DataFrame and a valid positive timeframe.
- Preserve incoming row order; never silently sort, drop, deduplicate or forward-fill.
- Require timezone-aware timestamps or an explicitly declared source timezone for naive timestamps.
- Reject ambiguous/nonexistent naive local timestamps during timezone localization.
- Convert timestamps to UTC for continuity and duplicate checks.
- Count duplicate timestamps and out-of-order transitions.
- Count actual missing expected bars, not merely the number of gaps.
- Reject non-numeric/non-finite OHLC values and invalid OHLC relationships.
- Calculate a raw-file SHA-256 and a deterministic normalized-data SHA-256.
- Return PASS only when every required gate passes; otherwise return STATE_UNKNOWN_ABORT.

## Important limitation

A timestamp interval mismatch is reported as a continuity failure. This initial implementation has no market-session calendar or feed-outage allowlist. It is therefore appropriate only for datasets whose declared timeframe is expected to be continuous. Instrument/session-specific expected gaps require a separately reviewed calendar policy; they must not be silently accepted.

## Usage

Install the optional data dependencies:

```bash
pip install -e ".[data]"
```

Example:

```python
from research.labs.data_validation import DataValidationEngine, ValidationConfig

engine = DataValidationEngine(
    "data/raw/instrument_1m.parquet",
    ValidationConfig(
        timeframe="1min",
        target_timezone="America/New_York",
        source_timezone=None,  # Set only if the Parquet index is naive and its source timezone is known.
    ),
)
validated = engine.load_and_validate()
print(engine.generate_report())
```

## Status boundary

A PASS means only that this validator's declared structural checks passed. It does not establish source authenticity, instrument identity, absence of look-ahead, market representativeness, spread/slippage validity, or strategy profitability.

`LIVE_EXECUTION=BLOCKED`, `capital_plane_mode=VERIFY_ONLY`, `FINAL_EXECUTION_AUTHORIZATION=false`, and `research_capital_authority=false` remain external governance requirements.
