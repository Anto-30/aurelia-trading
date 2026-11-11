# ADR-003: Quarantine the legacy R_100 prospective research pipeline

- **Status:** Owner-delegated research policy accepted; implementation pending independent review and merge
- **Date:** 2026-11-11
- **Scope:** Research workflows and research archive tooling only
- **Authority:** ATOS v2.0 Master Build & Research Specification, §4 and §5

## Context

The canonical `main` branch contained `.github/workflows/r100-prospective-oos.yml` with three triggers: pushes to `main`, manual dispatch, and a 15-minute schedule. It collected Deriv R_100 observations, recovered prior observations from GitHub Actions artifacts, and uploaded a persistent archive with a 30-day retention period.

The same branch contained `research/r100_prospective_oos_archiver.py`, whose archive function serialized observation rows to a file.

The owner-delegated ATOS v2.0 specification excludes Deriv synthetic indices from FX order-flow/SMC research and explicitly quarantines all R_100 artifacts from the EURUSD/XAUUSD programme. It also limits Deriv API-derived content to ephemeral caching of no more than 24 hours.

The current Deriv API Users Terms are Version R26|03, last updated 16 October 2026. Section 2.1 prohibits storing content derived from or accessed through the API; §2.3 permits caching such content for up to 24 hours. Official terms: https://deriv.com/terms-and-conditions/api-users

## Decision

1. Remove automatic push and scheduled triggers from the R_100 workflow.
2. Retain only a manual, non-collecting quarantine-status workflow. It performs no checkout, network request, market-data collection, or artifact upload.
3. Disable the callable R_100 collector module itself: `collect_once` and the CLI `main` fail closed before any network request or output write; remove the Deriv transport dependency from that module.
4. Make `save_state` and `seal_r100_archive` fail closed so new durable R_100 collector state or archives cannot be created through either legacy writer.
5. Retain `load_state` and `verify_sealed_archive` only as read-only historical inspection/integrity helpers. A successful hash check is not evidence eligibility.
6. Mark all historical R_100 observations, reports, and archives as quarantined. They are not evidence for EURUSD/XAUUSD FX research, OB+FVG Track A, Track B, or strategy promotion.
7. Preserve `config/LIVE_LOCK.yaml` and all capital, execution, release, and risk-authority files unchanged.

## Alternatives considered

- **Shorten artifact retention from 30 days to 24 hours:** rejected. It would continue a synthetic-index research stream that the owner has explicitly quarantined and would still create unnecessary API-derived archives.
- **Keep collecting but label reports as non-production:** rejected. The owner has excluded R_100 artifacts from the FX programme, and the API storage restriction remains applicable.
- **Move the collector to another persistent store:** rejected. Changing storage location does not resolve the research-scope exclusion or the API content-storage restriction.

## Consequences and required follow-up

- After this change is merged, the mainline R_100 workflow will no longer collect, recover, or upload new observations.
- This change does **not** delete historical GitHub Actions artifacts created by earlier runs. Those artifacts require separate authorized deletion by a repository administrator; they must not be downloaded, reused, or cited as FX/SMC evidence in the meantime.
- The legacy R_100 collector remains in the repository only for compatibility with historical analytical helpers and tests. Its direct collection and persistence entry points now fail closed.
- No baseline or R_100 collection rerun is permitted.
- The change does not modify production architecture, broker authentication, live execution, capital sizing, or `LIVE_LOCK`.
- Merge sequencing: this branch is based on the hardened head of PR #292. PR #292 must first complete independent security review and merge to `main`; this quarantine change then requires its own review against the updated `main`.

## Owner ratification

The quarantine policy is owner-delegated by ATOS v2.0 §4, effective 2026-11-11. Implementation remains subject to code review and required repository checks.
