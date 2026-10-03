# AURELIA Runtime Baseline — 2026-10-03

The historical v1.27 runtime source is not present. This branch explicitly designates a new native runtime baseline and does not reconstruct the missing source.

Implemented control families include authority and hard gates, authorization leases, account identity binding, state-machine enforcement, UNKNOWN handling, event hashing, append-only journaling, idempotency, execution fencing, circuit breaking, capital ledger hooks, reconciliation, watchdog/readiness, decision replay, prospective OOS validation, probability calibration/drift helpers, deployment packaging, and research/capital separation.

The baseline is non-live by construction: live trading is disabled and final execution authorization is false. No production evidence is fabricated.