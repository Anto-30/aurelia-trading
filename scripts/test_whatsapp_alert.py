from __future__ import annotations

import json

from runtime.notifications.whatsapp import WhatsAppAlertSink


def main() -> int:
    result = WhatsAppAlertSink.from_env().send_now(
        "RUNTIME_STARTUP",
        {
            "runtime_version": "whatsapp-smoke-test",
            "LIVE_EXECUTION": "BLOCKED",
            "capital_plane_mode": "VERIFY_ONLY",
        },
    )
    print(json.dumps({"component": "AURELIA", "whatsapp_test": result}, sort_keys=True))
    return 0 if result.get("status") == "SENT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
