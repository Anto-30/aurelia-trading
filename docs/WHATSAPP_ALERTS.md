# AURELIA WhatsApp Alerts

AURELIA exposes operational WhatsApp alerts through Twilio's Programmable Messaging API. The sink is attached to the append-only event journal, fails closed when unconfigured, deduplicates repeated events, strips credential-like fields from alert summaries, and never participates in capital authorization or execution.

## Railway configuration

Set these as protected Railway variables/secrets:

- AURELIA_WHATSAPP_ALERTS=true
- AURELIA_WHATSAPP_TO=+254714697623
- TWILIO_ACCOUNT_SID=AC...
- Either TWILIO_API_KEY=SK... + TWILIO_API_SECRET=..., or TWILIO_AUTH_TOKEN=...
- TWILIO_WHATSAPP_FROM=whatsapp:+<approved-sender>
- TWILIO_CONTENT_SID=HX... for proactive notifications outside the WhatsApp customer-service window

Optional:

- TWILIO_STATUS_CALLBACK_URL=https://<worker-domain>/twilio/status
- TWILIO_ALLOW_FREEFORM=true only during an active 24-hour customer-service window
- TWILIO_HTTP_TIMEOUT_SECONDS=8
- AURELIA_WHATSAPP_DEDUPE_SECONDS=300

Never commit Twilio credentials or secrets.

## WhatsApp template

Create an approved Utility Content Template such as:

AURELIA alert: {{1}} — {{2}}

The runtime passes the event type as variable 1 and a sanitized compact event summary as variable 2.

Twilio currently requires an approved template for business-initiated WhatsApp messages outside the 24-hour customer-service window. Approved templates are sent through the Messages API using ContentSid and ContentVariables.

## Sandbox testing

For first testing, use the WhatsApp test environment shown in Twilio Console and enroll +254714697623 in that specific sandbox/testing environment. Sandbox enrollment is required before messages can be delivered, and the Sandbox is for testing/discovery rather than production.

## Smoke test

After Twilio and Railway are configured:

python scripts/test_whatsapp_alert.py

Expected structure:

{"component":"AURELIA","whatsapp_test":{"message_sid":"...","message_status":"queued","status":"SENT"}}

A real WhatsApp delivery is the final external acceptance signal.

## Alert coverage

Alerts are emitted for runtime startup/failure, watchdog protection, kill-switch activation or blocked clearance, broker submission uncertainty/rejection/acceptance, contract settlement, and reconciliation mismatches. Healthy reconciliation events are filtered.

Notification failure cannot change the journal, readiness state, capital authorization, live lock, kill switch, or order-execution decision.
