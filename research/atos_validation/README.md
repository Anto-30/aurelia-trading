# ATOS v2.0 research validation

## Safety boundary
Research only. This package has no order-submission method and must not be wired directly to Layer 6 or the execution adapter. The canonical `config/LIVE_LOCK.yaml` is intentionally unchanged. `config/STAGING_PAPER.yaml` is a separate paper-mode profile and cannot override the canonical lock.

## Data
The research history client uses Deriv's documented `ticks_history` candle response on `wss://ws.derivws.com/websockets/v3?app_id=YOUR_APP_ID`. See https://developers.deriv.com/docs/data/ticks-history/. The API App ID is configuration, not an access token. The history client requires `DERIV_APP_ID` in its environment and never accepts an account token. It validates exact UTC candle boundaries, complete coverage, OHLC ordering, finite prices, and duplicate timestamps; it rejects truncation/gaps rather than silently deduplicating or filling. Deriv synthetic-index candles do not provide exchange-traded volume, so volume remains missing.

Fetch a complete historical interval and write a normalized CSV plus a SHA-256 manifest with:
```bash
export DERIV_APP_ID="<your numeric Deriv application ID>"
python scripts/fetch_deriv_history.py \
  --symbol R_100 \
  --start 2025-10-21T00:00:00Z \
  --end 2026-10-21T00:00:00Z \
  --granularity 60 \
  --out data/deriv/R_100_1m.csv
```
For a 24-month study, move `--start` back to the corresponding UTC boundary. The endpoints must align to the selected granularity. The CLI prints bar count and hashes, not account information. Store the generated CSV and manifest as a versioned research artifact; do not invent missing volume, execution costs, or trade outputs. Network/history limits and symbol availability can still block a requested interval, in which case there is no qualified dataset.

After downloading, verify that the CSV has not changed and that its coverage matches the manifest:
```bash
python scripts/verify_deriv_history_manifest.py data/deriv/R_100_1m.csv
```
The verifier checks the manifest hash, CSV hash, exact timestamp sequence, row count, OHLC invariants, and missing-volume policy. Keep the CSV and manifest together.

## Four-model trade ledger
The four-model evaluator accepts only a caller-produced ledger with timezone-aware timestamps, nonnegative realized costs in R, all four required strategy IDs, and the same fold IDs for every model. Provide explicit zero-trade fold records rather than omitting a fold. After a strategy-specific replay has generated verified net-cost inputs, run:
```bash
python -m research.atos_validation.four_model_backtest path/to/audited_trades.csv \
  --out artifacts/four_model_metrics.csv \
  --fold-out artifacts/four_model_fold_metrics.csv
```
The aggregate and fold-level files are labelled from the exact ledger SHA-256. This is a metric calculator, not a strategy simulator: it must not be run on example or fabricated data and then presented as evidence of edge.

The repository also has a manual GitHub Actions workflow, `Deriv historical research data ingestion`, which collects the same public history and uploads the CSV plus manifest as a 90-day artifact. After the workflow has been reviewed and merged to `main`, open **Actions → Deriv historical research data ingestion → Run workflow** and supply a numeric Deriv App ID, symbol, UTC start/end, and granularity. An App ID is not an account token; do not enter an account token in workflow inputs. The manual workflow defaults are set to the requested historical interval 2022-10-21T00:00:00Z through 2024-10-21T00:00:00Z. Run it separately for granularity 60 (1m) and 900 (15m). This older period is a research-development history window, not a prospective sealed OOS window. For reproducibility, preserve the downloaded manifest alongside the data and record the exact artifact/run identifier before analysis.

## Validation protocol
1. Sort and deduplicate source data, preserve missingness, and verify symbol availability/contract semantics.
2. Reserve the newest three calendar months by timestamp before any fitting or feature/parameter selection. Store its boundaries and hash in an immutable manifest.
3. Within older development data, run rolling WFA. Train all transforms and the HMM only on each training window. Predict subsequent held-out observations causally.
4. Replay each of the four models on identical market data and fold boundaries. Include spread, payout, commission (if contractually applicable), slippage, and latency assumptions sourced from observed contract quotes/fills; fail closed if costs are unavailable. Do not infer a universal synthetic-index commission or use invented volume.
5. Report net expectancy in R, profit factor, maximum drawdown, sample size, fold variance, confidence intervals, and fold-by-fold results. Account for multiple model/parameter trials and overlapping trades. Degradation above a preregistered 15–20% threshold triggers review/fallback; it is not proof of overfit.
6. Evaluate the sealed three-month OOS exactly once after choices are frozen. A failed/ambiguous OOS or cost source means no promotion.
7. Run paper mode and telemetry before any release review. Latency >200 ms is an alert threshold, not a guarantee of acceptable fills.

## Important limitations
- HMM states are unlabeled; regime names are heuristic mappings and can change between fits.
- The HMM uses Gaussian emissions and an approximate mapping; Alpha–Beta filtering should be compared against the standard HMM, MA control, and unfiltered MSNR.
- The four-model script consumes an audited trade ledger. It does not generate authentic MSNR trades from candles or invent model outputs. Strategy-specific trade generation and Deriv contract payoff/cost adapters remain required.
- ATR sizing requires the actual contract's monetary value per price unit and stop semantics. For fixed-payout contracts without a conventional stop, use stake/payout loss bounds rather than treating ATR sizing as a stop-loss guarantee.
- No live trading, real orders, or capital authorization is implemented.


## Hash-chained trade decisions and nine-file evidence output

Use `research/atos_validation/audited_ledger.py` to instrument the frozen strategy replay. It records every accepted, rejected, or no-trade decision and each completed trade, binds each record to the exact data and per-model configuration hashes, and enforces signal-candle N-1 to entry-candle N timing. The strategy replay must still supply the real signals, entry/exit values, P&L, and observed cost inputs; this helper is not a strategy simulator.

Verify the JSONL and its companion manifest before analysis:

```bash
python -m research.atos_validation.audited_ledger artifacts/trades/audited_trades.jsonl
```

The nine-file evidence builder is `scripts/build_release_evidence.py`. It verifies the history CSV against its manifest and the trade ledger against its manifest, derives only those metrics supported by its source files, emits null for unknown metrics, and explains missing fields in `evidence/evidence_notes.md`. It refuses to overwrite existing evidence unless `--overwrite` is explicitly supplied. `strategy_eligibility.eligible_for_live_unlock` always remains false.

See `docs/AUDITED_LEDGER_AND_EVIDENCE.md` for the 1m/15m backfill, pacing, required source reports, freeze protocol, and Issue #185 hash anchoring. The resulting evidence is incomplete until the real dataset, simulator-generated ledger, protected broker lifecycle, recovery, 3,600-second soak, calibration, costs, deployment review and independent approval have been recorded.
