# AURELIA Current Operational State — 2026-10-07

## Source of truth

- Repository: `Anto-30/aurelia-trading`
- Canonical branch: `main`
- Latest observed tip: `99a9a0da48ed2dde61260e68c4481a985e83f369`
- Live-release control: `config/LIVE_LOCK.yaml`
- Intelligence routing: `config/intelligence_source_routing.json`
- Intelligence routing assurance: `assurance/test_intelligence_source_routing.py`

## Engineering changes observed

The latest repository work continues the prospective R100 research hardening and adds a bounded intelligence-source routing contract.

The R100 work now:
- prevents a prospective campaign from sealing while unresolved pending observations remain;
- stops new candidate emission after campaign end while allowing pending observations to settle;
- rolls a sealed campaign into a new research state;
- preserves immutable campaign/source provenance;
- requires measurable probability reliability rather than treating sample size alone as calibration;
- rejects out-of-policy confidence rather than clipping it.

The intelligence routing layer maps GitHub, CodeRabbit, Next Stock Outlook, The Fly Market Intelligence, Sixtyfour Intelligence, Code Tytor: Python, Notion, and Outlook/Email to specialist research/engineering roles. The routing registry explicitly denies capital authority, live-order authority, production deployment authority, secret access, and external-code execution by default.

## Assurance

A dedicated regression contract exists for the routing layer. Code Tytor expert review reported zero issues in the test implementation.

The current GitHub connector reports no status checks attached to the latest documentation commit. This is not treated as a CI pass. Local direct network execution against GitHub was unavailable in the Python sandbox, so no unsupported local CI result is claimed.

## Capital safety

`config/LIVE_LOCK.yaml` remains:

- `live_trading_enabled: false`
- `FINAL_EXECUTION_AUTHORIZATION: false`
- `LIVE_EXECUTION: BLOCKED`
- `capital_plane_mode: VERIFY_ONLY`

No research/intelligence source has capital authority.

## Production blockers still outstanding

The previously verified blockers remain material unless fresh evidence proves otherwise:

1. Railway production worker/plan availability.
2. Authenticated Deriv runtime session using protected credentials.
3. Broker-confirmed end-to-end transaction/fill lifecycle.
4. Post-transaction ledger/reconciliation evidence.
5. Production-worker 3,600-second soak.
6. Prospective multi-day OOS qualification.
7. Probability calibration/drift qualification.
8. Net execution-cost/economics qualification, including at least 100 matched quoted-contract observations with positive mean net return before the research campaign can report `RESEARCH_QUALIFIED`.
9. Final evidence-backed release-gate decision.

Passing engineering tests or receiving a research recommendation does not satisfy these gates.

## Intelligence-source authority contract

All external intelligence follows:

`source -> specialist agent -> normalized evidence -> provenance/confidence -> deterministic validation -> existing release gate`

The capital plane remains sovereign. External agents, plugins, MCP sources, emails, stock-pick feeds, market-news feeds, and research repositories cannot directly authorize or submit capital-moving actions.

## Current decision

`FINAL_EXECUTION_AUTHORIZATION=false`

`LIVE_EXECUTION=BLOCKED`

`LIVE_ORDERS=0`

This record is an operational status snapshot, not a live-capital authorization.
