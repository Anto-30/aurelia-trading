# AURELIA Runtime Event and Incident Contract — 2026-10-03

Status: control specification; not live authorization.

## Event envelope
Every execution lifecycle event should carry event_id, decision_id, intent_id, event_type, event_time_utc, runtime_commit, configuration_digest, strategy_id/version/hash, account_id, symbol, market_data_time_utc, probability/status, requested_stake, approved_stake, broker_transaction_id when known, lifecycle_state, ledger_reference, reconciliation_status, invariant_status, and correlation_id.

Events are append-only and tamper-evident. Dashboards are not authoritative records.

## Incident lifecycle
HEALTHY → DEGRADED → CAPITAL_PROTECTED → RECOVERY → VERIFIED → RESUME.

CAPITAL_PROTECTED is required for stale/unverified balance, account mismatch, ambiguous broker outcome, duplicate intent, ledger mismatch, unexplained capital delta, stale market data, temporal-integrity failure, runtime/configuration hash mismatch, expired authorization/evidence, risk/firewall/watchdog failure, or kill-switch activation.

## Recovery invariant
Recovery must establish broker-side truth before any new order request. UNKNOWN remains UNKNOWN until reconciled; restart is not proof of recovery.

## Restart invariant
After process restart, pending intents must be restored and reconciled against broker transaction state before new execution intents are permitted.

## Concurrency invariant
Only one execution authority may act on a logical intent. Unique intent IDs and broker transaction IDs must be enforced at the persistence boundary.

## Capital anomaly invariant
Every balance change must be classified as a broker-confirmed trade, explicit account adjustment, or unresolved discrepancy. Unresolved discrepancy blocks new exposure.

## Economic attribution
Store gross result, execution costs, and net result separately. Missing costs remain UNKNOWN, not zero.

## Clock invariant
Decision time, market-data time, broker time, and persistence time are retained separately. Future-dated market data relative to decision time is invalid.

## Evidence rule
A passing unit or assurance test proves only the scenario exercised by that test. Native runtime behavior is unproven until the native runtime executes the scenario.