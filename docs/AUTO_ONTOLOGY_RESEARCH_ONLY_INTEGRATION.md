# NVIDIA Auto Ontology — AURELIA isolated research integration

**Status:** contract prototype only; not deployed or connected.  
**Upstream pin reviewed:** `NVIDIA/auto-ontology@caced11e69e19663dfa0f73778dbecbcb71e87a0`.  
**Permission boundary:** research-only.  
**Capital authority:** false. **Live order submission:** false.

## Purpose

Auto Ontology may provide semantic discovery over sanitized, immutable AURELIA research exports. It is not a trading engine, strategy optimizer, broker adapter, source of capital authorization, or replacement for AURELIA's deterministic Layer 6 and capital plane.

The first deliverable in this branch is a local, dependency-free evidence contract under `research/auto_ontology`. It does not import NVIDIA packages, connect to a database, execute SQL, invoke MCP, or make network requests.

## Data boundary

Only a separately approved research export may be considered. Never connect Auto Ontology to:
- the canonical capital ledger or production trading database;
- broker account/session/transaction endpoints;
- Deriv PATs, OAuth refresh tokens, API keys or other credentials;
- signing keys, operator reset material, LIVE_LOCK or deployment secrets.

Use a dedicated read-only database principal against a separate analytics database or immutable snapshot. Enforce schema/table allowlists, query timeouts, row/byte limits, network egress restrictions and per-user authorization outside this prototype.

## Evidence envelope

Every record must carry:
- immutable evidence identifier and source system/reference;
- source Git commit and SHA-256 dataset/payload digests;
- strategy identifier/version, timeframe, units and grain;
- decision time, feature availability time and observation time with explicit timezone;
- explicit PASS, FAIL or UNKNOWN status;
- RESEARCH scope and explicit false capital/live-order authority flags.

UNKNOWN remains UNKNOWN and is never promoted to PASS. Feature availability after the decision timestamp is rejected.

## Query boundary

A future adapter must accept only exact, independently reviewed query templates. Arbitrary generated SQL is not executable. A read-only MCP endpoint is not a sufficient security boundary: the database principal, schema permissions, private network, tenant identity and query resource limits must independently enforce read-only access.

The prototype's `QueryPolicy` only compares query text against an exact template allowlist; it does not parse SQL, connect to a database, or execute a query. Do not treat it as a substitute for database-level least privilege.

## Upstream deployment constraints

Before any isolated deployment:
1. Complete the quarantined repository scan, SBOM, license, vulnerability and image provenance reviews.
2. Use a segregated self-hosted non-production host with no network route to broker or production capital services.
3. Configure Vault completely and verify that no plaintext credential fallback is possible. Do not enter credentials until this is independently proven.
4. Keep the ingestion service private; its mutation endpoints must not be internet-exposed.
5. Keep the FastAPI service private and do not trust a caller-supplied identity header as authentication.
6. Use a dedicated read-only Postgres role and a sanitized research-only dataset.
7. Test cross-user isolation, SQL permission boundaries, join fanout, stale/superseded evidence, nulls, timezone handling, truncation, reproducibility and no-lookahead semantics.
8. Compare all decision-relevant outputs with deterministic Python truth sets and preserve query text, parameters, returned row counts, hashes, timestamps and truncation metadata.

## Explicit non-goals

This integration does not authorize or enable trading. It cannot prove strategy profitability, Deriv account identity, broker transaction lifecycle, runtime signing identity, persistent deployment readiness, a 3,600-second soak, or final release authorization.

`config/LIVE_LOCK.yaml` remains unchanged. AURELIA's capital plane and broker execution firewall remain the sole authorities for any future separately approved execution path.
