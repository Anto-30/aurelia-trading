from __future__ import annotations

from pathlib import Path
import json


class AuditQuery:
    def __init__(self, journal_path: str | Path):
        self.path = Path(journal_path)

    def _events(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def events_for_intent(self, intent_id: str) -> list[dict]:
        return [e for e in self._events() if e.get("correlation_id") == intent_id or e.get("payload", {}).get("intent_id") == intent_id]

    def blocked_decisions(self) -> list[dict]:
        return [e for e in self._events() if e.get("event_type") in {"AUTHORIZATION_DECISION", "PRE_SUBMISSION_BLOCKED"} and not e.get("payload", {}).get("allowed", True)]

    def unknown_events(self) -> list[dict]:
        return [e for e in self._events() if "UNKNOWN" in str(e.get("event_type", ""))]
