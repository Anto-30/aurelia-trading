# AURELIA WhatsApp Alerts

AURELIA's append-only event journal supports outbound WhatsApp alerts. The existing Twilio provider remains the default; this branch adds Meta WhatsApp Cloud API as an explicit alternative. Alerts never authorize trades, alter Layer 6 decisions, clear the kill switch, or enable live execution.

## Select provider

Set `AURELIA_WHATSAPP_PROVIDER=meta` to select Meta Cloud API, or `twilio` to keep the existing provider. Unknown values fail closed and do not silently switch providers. Alerts remain disabled unless `AURELIA_WHATSAPP_ALERTS=true`.

## Required Meta configuration

Add these to a protected GitHub Actions Environment or production-host secret manager. Never put token values in Git, repository variables, issue comments, chat, or logs.

- `META_WHATSAPP_ACCESS_TOKEN`: System User access token with `whatsapp_business_messaging` permission.
- `META_WHATSAPP_PHONE_NUMBER_ID`: numeric sender phone-number ID from WhatsApp API Setup.
- `META_WHATSAPP_TO`: recipient in E.164 format, e.g. `+2547XXXXXXXX`.
- `META_WHATSAPP_TEMPLATE_NAME`: exact name of an approved template with two body text placeholders.
- `META_WHATSAPP_TEMPLATE_LANGUAGE`: exact approved language, e.g. `en_US`.
- `META_WHATSAPP_API_VERSION`: currently supported Graph API version in `vNN.N` form; verify current support in Meta documentation.

Optional: `META_WHATSAPP_HTTP_TIMEOUT_SECONDS=8`, `AURELIA_WHATSAPP_DEDUPE_SECONDS=300`. Enable `AURELIA_WHATSAPP_ALERTS=true` only after the smoke test. Parser checks value shape, not token validity/scopes, recipient eligibility, sender ownership or template approval.

## Meta setup on Android

1. Open your app in [Meta for Developers](https://developers.facebook.com/) and configure the WhatsApp product.
2. In WhatsApp > API Setup, find the WhatsApp Business Account and sender Phone Number ID. Start with Meta's test sender if available.
3. Add your recipient as an allowed test recipient and complete verification.
4. Send Meta's official `hello_world` template from API Setup. Confirm it arrives before connecting AURELIA.
5. For unattended use, create a System User in the correct Business Portfolio, assign the app and WhatsApp assets, and issue a suitably scoped token. Do not rely on a short-lived dashboard token.
6. Create a Utility template and obtain approval. It must have two body text placeholders, e.g. `AURELIA alert: {{1}} — {{2}}`. Record exact template name and language.
7. Store required values as protected secrets in the deployment environment. Keep the recipient number private and out of repository documentation.
8. Run `python scripts/test_meta_whatsapp_alert.py` from the authorized runtime with secrets injected. Never run it in an untrusted fork.
9. A returned Meta message ID confirms API acceptance, not device delivery. Verify receipt in WhatsApp and inspect delivery status.
10. Only after verification, set `AURELIA_WHATSAPP_PROVIDER=meta` and enable alerts in the reviewed deployment environment. Keep live trading disabled while validating.

## Smoke test

```sh
python scripts/test_meta_whatsapp_alert.py
```

Outbound-only alerts need no inbound webhook. Delivery receipts/replies would require a separately secured webhook with signature verification and replay protection.

## Safety

Allowlisted startup, data/session uncertainty, watchdog, kill-switch, broker outcome, settlement and unhealthy-reconciliation events can alert. Healthy reconciliation is filtered. Credential-like and phone-related payload keys are excluded from summaries. Notification failures cannot alter the append-only journal or capital-control chain.
