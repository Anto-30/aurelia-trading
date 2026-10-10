# Crucix Intelligence Integration Review

**Review date:** 2026-10-10  
**AURELIA source revision at review:** d376aa061811893d4058cf4ed7a17dfaf454b315

## Decision

Use the canonical Crucix source and the Market Shock Radar only as optional, read-only research context, behind a small AURELIA-owned adapter. Do not merge Crucix source code into the AURELIA Python runtime: the upstream project is AGPL-3.0-only, is a separate Node.js service, and has its own dependency/lifecycle boundary. Keep license notices and source availability obligations under review before any hosted rollout.

The connector is **disabled by default**. It has no order, release, or risk-control capability. If the service is unavailable, stale, malformed, or returns incomplete timestamps, AURELIA records an unknown/degraded advisory; it does not transform that failure into a trade signal.

## Repository disposition

| Repository | Pinned revision | Decision |
|---|---|---|
| [calesthio/Crucix](https://github.com/calesthio/Crucix) | `3db7068817e0c815df353fa0f19657c85142789d` | Preferred upstream candidate; AGPL-3.0-only; separate read-only sidecar |
| [heckel75/CRUCIX-Market-Shock-Radar](https://github.com/heckel75/CRUCIX-Market-Shock-Radar) | `0cbdbe287b57add55f921dd7f70e6723b422c458` | Optional end-of-day divergence context only; AGPL-3.0 |
| [Gui-Ni/crucix-intelligence](https://github.com/Gui-Ni/crucix-intelligence) | `09a2fb6f5f3da833a694ff58dca39f6836d3c73b` | Duplicate/mirror; not chosen as canonical; review its deployment workflow independently |
| [trxd/crucix](https://github.com/trxd/crucix) | `2936d44eea1d4f8ecc5b6318e18f1e3825454cd0` | Reject for production build: its Dockerfile fetches an unpinned upstream branch and a separate BusyBox binary |
| [StoneKolowaka/Crucix-backup](https://github.com/StoneKolowaka/Crucix-backup) | `0825d8a6828888b27bb643e8cc5e46611a5dadd9` | Historical backup only; not an alternate production source |
| [Salmonfourierseries203/Crucix](https://github.com/Salmonfourierseries203/Crucix) | `99ca19c20785ad9426c33b27842d8a9b3d75c665` | Quarantined: only a ZIP archive and README were present, and no license/dependency/source manifest was found |

Pinned revisions are review identities, not automatically trusted releases. Re-review on every revision change.

## Data interface

- Crucix data endpoint: `GET /api/data`. Its response includes `meta.timestamp`, source-count metadata, and per-source status.
- The Shock Radar emits `divergence.json` and `market-shock.json`. Both are explicitly separate, configurable read-only URLs.
- The connector applies a three-second request timeout, bounded JSON response size, rejects redirects, and refuses URLs containing embedded credentials.
- Raw story/headline text and LLM outputs are **not forwarded** to AURELIA agents. Only timestamps, source-health counts, freshness labels, warning counts, shock summary metadata, and divergence-state counts are emitted.
- Every event is labelled `capital_authority=false`, `trade_signal=false`, and `order_submission_permitted=false`.

Environment variables (configured on the runtime host; never commit secrets):

```text
AURELIA_CRUCIX_ENABLED=false
AURELIA_CRUCIX_DATA_URL=http://127.0.0.1:3117/api/data
AURELIA_CRUCIX_RADAR_URL=
AURELIA_CRUCIX_SHOCK_URL=
AURELIA_CRUCIX_POLL_SECONDS=300
AURELIA_CRUCIX_MAX_AGE_SECONDS=900
```

When Crucix is deployed in a separate Docker container, replace loopback with the container's private-network service name and ensure AURELIA and Crucix share only a private Docker network. Do not publish this unauthenticated research endpoint publicly.

## Strategy and instrument restrictions

Crucix's public data includes OSINT feeds, macro indicators, Yahoo Finance prices, and source-health metadata. That is not a substitute for Deriv's instrument-specific ticks, candles, contract specifications, spread/slippage, or execution evidence. The Shock Radar methodology uses daily market-close-aligned macro/ETF transformations. In the reviewed artifact, the latest market close was **2026-10-02**, generated on **2026-10-10**, with an **8-calendar-day lag** and a `lagging` freshness status. It must not be presented as current, and it cannot qualify MSNR scalping on a Deriv synthetic index.

No source in this family can open/close a trade, alter stake size, clear a kill switch, mark a strategy qualified, loosen risk limits, or set `LIVE_LOCK`. A future strategy may explicitly consume a freshness-qualified contextual feature, but it still has to pass AURELIA's existing instrument-specific qualification, out-of-sample, calibration, net-economics, and risk gates.

## Current go-live consequence

This integration does **not** unblock live execution. At the last verified release check, `config/LIVE_LOCK.yaml` still has `live_trading_enabled=false`, `FINAL_EXECUTION_AUTHORIZATION=false`, `LIVE_EXECUTION=BLOCKED`, and `capital_plane_mode=VERIFY_ONLY`. The latest GitHub secret-presence report also reported missing production host/SSH fields and incomplete Deriv account binding. No broker order is submitted by this change.
