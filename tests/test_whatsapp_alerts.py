from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runtime.notifications.whatsapp as whatsapp
from runtime.core.journal import AppendOnlyJournal
from runtime.notifications.whatsapp import WhatsAppAlertSink, WhatsAppConfig


class WhatsAppAlertTests(unittest.TestCase):
    def test_disabled_by_default_is_fail_closed(self):
        with patch.dict(os.environ, {"AURELIA_WHATSAPP_ALERTS": "false"}, clear=False):
            sink = WhatsAppAlertSink.from_env()
        self.assertFalse(sink.status()["enabled"])
        self.assertEqual(
            sink.send_now("BROKER_ACCEPTED", {"symbol": "R_100"})["status"],
            "DISABLED",
        )

    def test_enabled_configuration_requires_template_for_proactive_alerts(self):
        env = {
            "AURELIA_WHATSAPP_ALERTS": "true",
            "TWILIO_ACCOUNT_SID": "AC_TEST_ACCOUNT_SID",
            "TWILIO_API_KEY": "SK_TEST_API_KEY",
            "TWILIO_API_SECRET": "TEST_AUTH_MATERIAL",
            "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
            "AURELIA_WHATSAPP_TO": "+254714697623",
        }
        with patch.dict(os.environ, env, clear=False):
            for key in (
                "TWILIO_CONTENT_SID",
                "TWILIO_ALLOW_FREEFORM",
            ):
                os.environ.pop(key, None)
            sink = WhatsAppAlertSink.from_env()
        self.assertFalse(sink.status()["ready"])
        self.assertIn(
            "TWILIO_CONTENT_SID_REQUIRED_FOR_PROACTIVE_WHATSAPP",
            sink.status()["configuration_errors"],
        )

    def test_send_uses_content_template_and_keeps_transport_response(self):
        config = WhatsAppConfig(
            enabled=True,
            account_sid="AC_TEST_ACCOUNT_SID",
            api_key="SK_TEST_API_KEY",
            api_secret="TEST_AUTH_MATERIAL",
            auth_token=None,
            from_address="whatsapp:+14155238886",
            to_address="whatsapp:+254714697623",
            content_sid="HX_TEST_CONTENT_SID",
            allow_freeform=False,
            status_callback_url=None,
            timeout_seconds=8.0,
            dedupe_window_seconds=300.0,
            errors=(),
        )
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(
                    {"sid": "SM_TEST_MESSAGE", "status": "queued"}
                ).encode()

        def fake_urlopen(request, timeout):
            captured["body"] = request.data.decode()
            captured["timeout"] = timeout
            return FakeResponse()

        with patch.object(whatsapp, "urlopen", fake_urlopen):
            result = WhatsAppAlertSink(config).send_now(
                "BROKER_ACCEPTED",
                {
                    "symbol": "R_100",
                    "direction": "CALL",
                    "stake": 1.0,
                    "broker_transaction_id": "txn-1",
                },
            )

        self.assertEqual(result["status"], "SENT")
        self.assertIn("ContentSid=HX_TEST_CONTENT_SID", captured["body"])
        self.assertIn("R_100", captured["body"])

    def test_healthy_reconciliation_is_filtered(self):
        config = WhatsAppConfig(
            enabled=True,
            account_sid="AC_TEST_ACCOUNT_SID",
            api_key="SK_TEST_API_KEY",
            api_secret="TEST_AUTH_MATERIAL",
            auth_token=None,
            from_address="whatsapp:+14155238886",
            to_address="whatsapp:+254714697623",
            content_sid="HX_TEST_CONTENT_SID",
            allow_freeform=False,
            status_callback_url=None,
            timeout_seconds=8.0,
            dedupe_window_seconds=300.0,
            errors=(),
        )
        sink = WhatsAppAlertSink(config)
        self.assertEqual(
            sink.send_now(
                "RECONCILIATION",
                {"healthy": True, "difference": 0},
            )["status"],
            "FILTERED",
        )

    def test_journal_append_invokes_alert_sink_without_changing_journal_write(self):
        class FakeSink:
            def __init__(self):
                self.calls = []

            def emit(self, event_type, payload):
                self.calls.append((event_type, payload))

        with tempfile.TemporaryDirectory() as tmp:
            sink = FakeSink()
            journal = AppendOnlyJournal(Path(tmp) / "events.ndjson", alert_sink=sink)
            journal.append(
                {
                    "event_type": "KILL_SWITCH_ACTIVATED",
                    "payload": {"reason": "TEST"},
                }
            )
            self.assertEqual(
                sink.calls,
                [("KILL_SWITCH_ACTIVATED", {"reason": "TEST"})],
            )
            self.assertEqual(
                journal.read_all()[0]["event_type"],
                "KILL_SWITCH_ACTIVATED",
            )


if __name__ == "__main__":
    unittest.main()
