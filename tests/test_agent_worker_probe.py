from __future__ import annotations

from scripts.agent_worker_probe import connector_status_snapshot


class FakeFederation:
    def __init__(self, messages: dict[str, list[dict]]):
        self._messages = messages

    def messages_for(self, agent: str, *, limit: int = 100):
        return self._messages.get(agent, [])[:limit]


def test_connector_status_snapshot_uses_latest_supervisor_status() -> None:
    federation = FakeFederation(
        {
            "ClaudeCode": [
                {
                    "message_type": "CONNECTOR_STATUS",
                    "created_at": "2026-11-02T10:00:00+00:00",
                    "payload": {"provider_session": "NOT_CONFIGURED"},
                },
                {
                    "message_type": "CONNECTOR_STATUS",
                    "created_at": "2026-11-02T11:00:00+00:00",
                    "payload": {"provider_session": "CONFIGURED_COMMAND"},
                },
            ]
        }
    )
    assert connector_status_snapshot(federation, ("ClaudeCode",)) == {
        "ClaudeCode": "CONFIGURED_COMMAND"
    }


def test_connector_status_snapshot_marks_missing_provider_as_unknown() -> None:
    federation = FakeFederation({})
    assert connector_status_snapshot(federation, ("KimiK3",)) == {
        "KimiK3": "UNKNOWN"
    }
