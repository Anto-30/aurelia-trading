from pathlib import Path

from runtime.core.trade_counter import count_accepted_trades, read_journal, trade_count


def test_counts_unique_broker_accepted_trades():
    events = [
        {"event_type":"BROKER_ACCEPTED","occurred_at_utc":"2026-10-08T10:00:00Z",
         "payload":{"intent_id":"i1","broker_transaction_id":"t1"}},
        {"event_type":"BROKER_ACCEPTED","occurred_at_utc":"2026-10-08T10:01:00Z",
         "payload":{"intent_id":"i1","broker_transaction_id":"t1"}},
        {"event_type":"BROKER_ACCEPTED","occurred_at_utc":"2026-10-08T10:02:00Z",
         "payload":{"intent_id":"i2","broker_transaction_id":"t2"}},
        {"event_type":"PRE_SUBMISSION_BLOCKED","occurred_at_utc":"2026-10-08T10:03:00Z",
         "payload":{"intent_id":"i3"}},
    ]
    summary = trade_count(events)
    assert summary.accepted_trades == 2
    assert summary.unique_intents == 2
    assert summary.last_trade_at_utc == "2026-10-08T10:02:00Z"
    assert count_accepted_trades(events) == 2


def test_missing_journal_is_zero(tmp_path: Path):
    assert read_journal(tmp_path / "missing.ndjson") == []
    assert count_accepted_trades([]) == 0
