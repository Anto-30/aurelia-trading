from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Any


@dataclass(frozen=True)
class TradeCount:
    accepted_trades: int
    unique_intents: int
    last_trade_at_utc: str | None


def _accepted_key(event: Mapping[str, Any]) -> str | None:
    payload = event.get("payload")
    if not isinstance(payload, Mapping):
        return None
    txid = str(payload.get("broker_transaction_id") or "").strip()
    if txid:
        return f"tx:{txid}"
    intent_id = str(payload.get("intent_id") or "").strip()
    return f"intent:{intent_id}" if intent_id else None


def count_accepted_trades(events: Iterable[Mapping[str, Any]]) -> int:
    return trade_count(events).accepted_trades


def trade_count(events: Iterable[Mapping[str, Any]]) -> TradeCount:
    keys: set[str] = set()
    last: str | None = None
    for event in events:
        if str(event.get("event_type") or "") != "BROKER_ACCEPTED":
            continue
        key = _accepted_key(event)
        if key is None or key in keys:
            continue
        keys.add(key)
        occurred = str(event.get("occurred_at_utc") or "").strip()
        if occurred and (last is None or occurred > last):
            last = occurred
    return TradeCount(
        accepted_trades=len(keys),
        unique_intents=len({k for k in keys if k.startswith("intent:")}),
        last_trade_at_utc=last,
    )


def read_journal(path: str | Path) -> list[dict[str, Any]]:
    journal = Path(path)
    if not journal.exists():
        return []
    events: list[dict[str, Any]] = []
    with journal.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                events.append(value)
    return events
