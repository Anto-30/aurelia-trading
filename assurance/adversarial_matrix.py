"""Canonical non-live adversarial assurance scenario matrix."""
from __future__ import annotations

SCENARIOS = (
    ("STALE_MARKET_DATA", "stale_tick", "NO_TRADE"),
    ("DUPLICATE_TICK", "duplicate_market_event", "NO_TRADE"),
    ("OUT_OF_ORDER_TICK", "timestamp_reversal", "NO_TRADE"),
    ("MALFORMED_PRICE", "nan_or_invalid_price", "NO_TRADE"),
    ("FUTURE_MTF_SNAPSHOT", "higher_timeframe_timestamp_after_decision", "NO_TRADE"),
    ("DUPLICATE_INTENT", "same_id_second_worker", "NO_DUPLICATE_EFFECT"),
    ("CONCURRENT_INTENTS", "two_workers_same_signal", "SERIALIZE_OR_REJECT"),
    ("BROKER_TIMEOUT", "request_then_timeout", "RECOVER_BEFORE_RETRY"),
    ("BROKER_RESPONSE_LOST", "economic_effect_then_missing_response", "RECOVER_BEFORE_RETRY"),
    ("BROKER_UNKNOWN", "unknown_outcome", "NO_BLIND_RETRY"),
    ("WEBSOCKET_DISCONNECT", "stream_loss_mid_lifecycle", "ENTER_RECOVERY"),
    ("CRASH_AFTER_SUBMIT", "process_exit_after_submit", "RECOVER_BY_INTENT_ID"),
    ("CRASH_AFTER_ACK", "process_exit_after_ack", "RECOVER_BY_BROKER_ID"),
    ("CRASH_BEFORE_LEDGER", "result_persisted_without_ledger", "RECONCILE"),
    ("RESTART_WITH_KILL", "restart_while_kill_switch_on", "REMAIN_BLOCKED"),
    ("STALE_AUTHORIZATION", "authorization_age_exceeded", "NO_TRADE"),
    ("CONFIG_DRIFT", "runtime_hash_differs", "NO_TRADE"),
    ("ACCOUNT_MISMATCH", "intent_account_differs_from_authorized_account", "NO_TRADE"),
    ("INSUFFICIENT_FUNDS", "broker_affordability_rejection", "REJECT"),
    ("RECONCILIATION_MISMATCH", "broker_vs_ledger_difference", "FREEZE_NEW_ORDERS"),
    ("BACKUP_RESTORE", "restore_state_then_reconcile", "NO_DUPLICATE_EFFECT"),
    ("CREDENTIAL_BOUNDARY", "research_actor_requests_capital_action", "DENY"),
    ("SHADOW_DIVERGENCE", "shadow_and_authorized_path_disagree", "INVESTIGATE"),
    ("EVIDENCE_EXPIRY", "evidence_validity_window_exceeded", "REVALIDATE"),
    ("MULTIPLE_TESTING", "repeated_oos_trials", "ACCOUNT_FOR_TRIAL_COUNT"),
    ("DRIFT_ALERT", "probability_or_execution_distribution_drift", "SUSPEND_OR_REVIEW"),
)

def matrix_is_complete() -> bool:
    return len(SCENARIOS) >= 20 and all(len(row) == 3 for row in SCENARIOS)
