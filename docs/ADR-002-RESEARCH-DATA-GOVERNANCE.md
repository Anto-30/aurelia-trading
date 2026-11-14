# ADR-002: Licensed data, ephemeral broker feeds, and cross-source calibration

- **Status:** Adopted as the ATOS v2.0 research data policy; source coverage and ingestion remain gated
- **Date:** 2026-11-11
- **Scope:** Research data governance only
- **Owner authority:** ATOS v2.0 §§4-5

## Context

The research programme requires reproducible intraday FX data while respecting provider licenses and the difference between indicative/aggregated feeds and the broker's own executable quote stream. Data provenance, storage permissions, and feed-basis risk are part of the experiment, not administrative afterthoughts.

## Decision

### 1. Persistent archive

- **Primary candidate: TrueFX / Integral.** Use only for the license-permitted internal analysis purpose. Do not redistribute, publish, or disseminate source prices or licensed content. Official terms: https://www.truefx.com/truefx-terms-and-conditions/
- EURUSD is the first instrument. TrueFX registration, available history depth, export format, and the exact symbol list must be verified before ingestion. XAUUSD/metals coverage remains unverified until the registered account's instrument list is inspected.
- TrueFX/Integral data is an indicative/aggregated research feed, not a Deriv executable quote or a guarantee of fills.

### 2. Conditional and held sources

- **Dukascopy web export:** do not create a persistent database from website-export data under the restrictive reading of the published website terms. Gold persistence is blocked until JForex client-agreement terms are verified or written permission is obtained.
- **HistData.com:** hold. No ingestion until an explicit license covering the intended storage and internal research use is confirmed in writing.
- Backups and snapshots of licensed archives remain subject to the same restrictions. No redistribution or public artifacts.

### 3. Deriv API feed

- Treat Deriv API-derived market content as ephemeral. Do not persist raw candles, raw ticks, or price-level ledgers to Git, long-lived CI artifacts, or cloud storage.
- Enforce a hard cache TTL no longer than 24 hours, with expiry/deletion at read, job start/end, and termination where applicable.
- Persist aggregate research outputs and provenance only: provider, exact symbol, request parameters, retrieval time, code/version, and content checksum where permissible. A checksum must not be used as a way to retain or reconstruct restricted feed content.
- Review API Terms §3.1.6 IP-assignment language with qualified counsel before productization. This ADR is not legal advice.
- Official terms: https://deriv.com/terms-and-conditions/api-users

### 4. Cross-source calibration

TrueFX/Integral, Dukascopy, and Deriv are distinct liquidity/quote environments. Before relying on a level-based signal across venues:

1. Align timestamps and instrument basis over overlapping recent windows.
2. Quantify mid/bid/ask divergence, spread differences, gaps, and timing offsets.
3. Record the comparison window, timezone, symbols, transformations, and uncertainty.
4. Fail closed if the feeds are not sufficiently comparable for the hypothesis.
5. Treat a signal present on only one feed as a possible feed artifact, not proof of edge.

### 5. Data quality and reproducibility

Require monotonic timestamps, duplicate detection, gap/stale-tick/outlier flags, weekend/holiday handling, IANA timezone/DST conversion, documented bid/ask-vs-mid basis, and explicit truncation detection. NQ studies also require documented futures rolls and back-adjustment. Pin licensed snapshots by content hash, version ingestion code, fix random seeds, lock dependencies, and replay deterministically.

Deriv FX candle/tick feeds do not provide DOM or exchange-traded true volume. Tick imbalance and realized volatility may only be called proxies. Do not claim OFI, VPIN, or true-volume measures from those inputs.

## Alternatives considered

- **Persist raw Deriv feed data for convenience:** rejected because the owner policy and current API terms restrict storage.
- **Use free downloads as automatically licensed data:** rejected. Availability at zero price does not establish storage or research rights.
- **Use one source as ground truth across all venues:** rejected because feed divergence can create venue-specific artifacts.
- **Persist Dukascopy or HistData before written terms are resolved:** rejected under the conservative compliance interpretation.

## Consequences and open gates

- EURUSD via TrueFX is the first archive ingestion target, but implementation cannot begin until registration, history depth, symbol coverage, and file schema are verified.
- XAUUSD gold history remains blocked pending TrueFX coverage verification or a compliant Dukascopy JForex/permission route.
- HistData remains held.
- Deriv remains ephemeral only; no long-lived Deriv raw-feed archive or artifact.
- No research baseline may be rerun until the applicable P0 workflow/security and data-compliance controls are satisfied.

## Ratification

This policy is adopted for the Layer-9 research programme under the owner-delegated ATOS v2.0 specification effective 2026-11-11. Any change to a source, license interpretation, retention limit, or intended distribution requires a new ADR and owner ratification.
