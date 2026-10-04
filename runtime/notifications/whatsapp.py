from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
ACCOUNT_SID_RE = re.compile(r"^AC[0-9A-Za-z]{30,}$")
API_KEY_RE = re.compile(r"^SK[0-9A-Za-z]{20,}$")
CONTENT_SID_RE = re.compile(r"^HX[0-9A-Za-z]{10,}$")

ALERT_EVENT_TYPES = frozenset(
    {
        "RUNTIME_STARTUP",
        "PUBLIC_MARKET_DATA_UNKNOWN",
        "AUTHENTICATED_DERIV_SESSION_VERIFIED",
        "AUTHENTICATED_DERIV_SESSION_UNKNOWN",
        "WATCHDOG_PROTECT",
        "CONTINUOUS_RUNTIME_UNKNOWN",
        "AUTONOMOUS_RUNTIME_STARTED",
        "KILL_SWITCH_ACTIVATED",
        "KILL_SWITCH_CLEAR_BLOCKED",
        "BROKER_SUBMISSION_EXCEPTION",
        "BROKER_OUTCOME_UNKNOWN",
        "BROKER_ACCEPTED",
        "BROKER_REJECTED",
        "CONTRACT_SETTLED",
        "RECONCILIATION",
    }
)

class NotificationConfigurationError(ValueError):
    pass

@dataclass(frozen=True)
class WhatsAppConfig:
    enabled: bool
    account_sid: str
    api_key: str | None
    api_secret: str | None
    auth_token: str | None
    from_address: str
    to_address: str
    content_sid: str | None
    allow_freeform: bool
    status_callback_url: str | None
    timeout_seconds: float
    dedupe_window_seconds: float
    errors: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.enabled and not self.errors

    @classmethod
    def from_env(cls) -> "WhatsAppConfig":
        enabled = os.getenv("AURELIA_WHATSAPP_ALERTS", "false").strip().lower() == "true"
        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        api_key = os.getenv("TWILIO_API_KEY", "").strip() or None
        api_secret = os.getenv("TWILIO_API_SECRET", "").strip() or None
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip() or None
        from_address = _normalize_address(os.getenv("TWILIO_WHATSAPP_FROM", "").strip())
        to_address = _normalize_address(os.getenv("AURELIA_WHATSAPP_TO", "").strip())
        content_sid = os.getenv("TWILIO_CONTENT_SID", "").strip() or None
        allow_freeform = os.getenv("TWILIO_ALLOW_FREEFORM", "false").strip().lower() == "true"
        status_callback_url = os.getenv("TWILIO_STATUS_CALLBACK_URL", "").strip() or None

        try:
            timeout_seconds = max(
                2.0,
                min(15.0, float(os.getenv("TWILIO_HTTP_TIMEOUT_SECONDS", "8"))),
            )
        except ValueError:
            timeout_seconds = 8.0

        try:
            dedupe_window_seconds = max(
                30.0,
                min(3600.0, float(os.getenv("AURELIA_WHATSAPP_DEDUPE_SECONDS", "300"))),
            )
        except ValueError:
            dedupe_window_seconds = 300.0

        errors: list[str] = []
        if not enabled:
            return cls(
                enabled=False,
                account_sid=account_sid,
                api_key=api_key,
                api_secret=api_secret,
                auth_token=auth_token,
                from_address=from_address,
                to_address=to_address,
                content_sid=content_sid,
                allow_freeform=allow_freeform,
                status_callback_url=status_callback_url,
                timeout_seconds=timeout_seconds,
                dedupe_window_seconds=dedupe_window_seconds,
                errors=(),
            )

        if not ACCOUNT_SID_RE.fullmatch(account_sid):
            errors.append("TWILIO_ACCOUNT_SID_MISSING_OR_INVALID")
        if api_key and not API_KEY_RE.fullmatch(api_key):
            errors.append("TWILIO_API_KEY_MISSING_OR_INVALID")
        if api_key and not api_secret:
            errors.append("TWILIO_API_SECRET_MISSING")
        if api_secret and not api_key:
            errors.append("TWILIO_API_KEY_MISSING")
        if not ((api_key and api_secret) or auth_token):
            errors.append("TWILIO_CREDENTIALS_MISSING")
        if not to_address:
            errors.append("AURELIA_WHATSAPP_TO_MISSING_OR_INVALID")
        if not from_address:
            errors.append("TWILIO_WHATSAPP_FROM_MISSING_OR_INVALID")
        if content_sid and not CONTENT_SID_RE.fullmatch(content_sid):
            errors.append("TWILIO_CONTENT_SID_MISSING_OR_INVALID")
        if not content_sid and not allow_freeform:
            errors.append("TWILIO_CONTENT_SID_REQUIRED_FOR_PROACTIVE_WHATSAPP")

        return cls(
            enabled=True,
            account_sid=account_sid,
            api_key=api_key,
            api_secret=api_secret,
            auth_token=auth_token,
            from_address=from_address,
            to_address=to_address,
            content_sid=content_sid,
            allow_freeform=allow_freeform,
            status_callback_url=status_callback_url,
            timeout_seconds=timeout_seconds,
            dedupe_window_seconds=dedupe_window_seconds,
            errors=tuple(errors),
        )

class WhatsAppAlertSink:
    """Outbound WhatsApp alerts that cannot affect the capital-control chain."""

    def __init__(self, config: WhatsAppConfig | None = None) -> None:
        self.config = config or WhatsAppConfig.from_env()
        self._lock = threading.Lock()
        self._seen: dict[str, float] = {}

    @classmethod
    def from_env(cls) -> "WhatsAppAlertSink":
        return cls(WhatsAppConfig.from_env())

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "ready": self.config.ready,
            "configuration_errors": list(self.config.errors),
            "recipient_configured": bool(self.config.to_address),
            "sender_configured": bool(self.config.from_address),
            "content_template_configured": bool(self.config.content_sid),
        }

    def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        if event_type not in ALERT_EVENT_TYPES or not self.config.ready:
            return
        payload = payload if isinstance(payload, dict) else {}
        if not _should_alert(event_type, payload):
            return

        dedupe_key = hashlib.sha256(
            json.dumps(
                {
                    "event_type": event_type,
                    "payload": _sanitize_payload(payload),
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()

        now = time.monotonic()
        with self._lock:
            stale = [
                key
                for key, seen_at in self._seen.items()
                if now - seen_at > self.config.dedupe_window_seconds
            ]
            for key in stale:
                self._seen.pop(key, None)
            if dedupe_key in self._seen:
                return
            self._seen[dedupe_key] = now

        threading.Thread(
            target=self._send_background,
            args=(event_type, payload),
            name="aurelia-whatsapp-alert",
            daemon=True,
        ).start()

    def send_now(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.config.enabled:
            return {"status": "DISABLED"}
        if not self.config.ready:
            return {
                "status": "NOT_CONFIGURED",
                "errors": list(self.config.errors),
            }
        if event_type not in ALERT_EVENT_TYPES:
            return {"status": "IGNORED_EVENT"}
        if not _should_alert(event_type, payload or {}):
            return {"status": "FILTERED"}
        return self._send(event_type, payload or {})

    def _send_background(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            self._send(event_type, payload)
        except Exception as exc:
            print(
                f"AURELIA_WHATSAPP_ALERT_FAILED:{type(exc).__name__}",
                file=sys.stderr,
            )

    def _send(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        summary = _summary(event_type, payload)
        form: dict[str, str] = {
            "From": self.config.from_address,
            "To": self.config.to_address,
        }
        if self.config.content_sid:
            form["ContentSid"] = self.config.content_sid
            form["ContentVariables"] = json.dumps(
                {"1": event_type, "2": summary},
                separators=(",", ":"),
            )
        elif self.config.allow_freeform:
            form["Body"] = f"AURELIA ALERT | {event_type} | {summary}"
        else:
            raise NotificationConfigurationError(
                "TWILIO_CONTENT_SID_REQUIRED_FOR_PROACTIVE_WHATSAPP"
            )

        if self.config.status_callback_url:
            form["StatusCallback"] = self.config.status_callback_url

        credentials_user = self.config.api_key or self.config.account_sid
        credentials_secret = self.config.api_secret or self.config.auth_token
        if not credentials_user or not credentials_secret:
            raise NotificationConfigurationError("TWILIO_CREDENTIALS_MISSING")

        auth = base64.b64encode(
            f"{credentials_user}:{credentials_secret}".encode("utf-8")
        ).decode("ascii")

        request = Request(
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.config.account_sid}/Messages.json",
            data=urlencode(form).encode("utf-8"),
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "aurelia-whatsapp-alerts/1",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"TWILIO_HTTP_{exc.code}") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(
                f"TWILIO_TRANSPORT_{type(exc).__name__}"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"TWILIO_RESPONSE_INVALID:{type(exc).__name__}"
            ) from exc

        return {
            "status": "SENT",
            "message_sid": str(body.get("sid", "")),
            "message_status": str(body.get("status", "")),
        }

def _normalize_address(value: str) -> str:
    if not value:
        return ""
    raw = value.strip()
    if raw.startswith("whatsapp:"):
        raw = raw.split(":", 1)[1]
    if not E164_RE.fullmatch(raw):
        return ""
    return f"whatsapp:{raw}"

def _should_alert(event_type: str, payload: dict[str, Any]) -> bool:
    if event_type == "RECONCILIATION":
        return not bool(payload.get("healthy"))
    return True

def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sensitive_fragments = ("token", "secret", "password", "credential")
    result: dict[str, Any] = {}
    for key, value in payload.items():
        normalized = str(key).lower()
        if any(fragment in normalized for fragment in sensitive_fragments):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[str(key)] = value
    return result

def _summary(event_type: str, payload: dict[str, Any]) -> str:
    payload = _sanitize_payload(payload)
    ordered_keys = {
        "BROKER_ACCEPTED": (
            "symbol", "direction", "stake", "broker_transaction_id",
            "contract_id", "decision_id",
        ),
        "CONTRACT_SETTLED": (
            "symbol", "direction", "stake", "net_delta", "post_balance",
            "contract_id", "reconciliation_healthy",
        ),
        "RECONCILIATION": ("healthy", "difference", "reason"),
        "RUNTIME_STARTUP": (
            "runtime_version", "live_execution", "LIVE_EXECUTION",
            "capital_plane_mode",
        ),
        "AUTONOMOUS_RUNTIME_STARTED": (
            "environment", "currency", "symbol_count", "verified_balance",
        ),
        "KILL_SWITCH_ACTIVATED": ("reason",),
        "KILL_SWITCH_CLEAR_BLOCKED": ("reason",),
        "WATCHDOG_PROTECT": ("reason",),
        "BROKER_SUBMISSION_EXCEPTION": ("intent_id", "error_class"),
        "BROKER_OUTCOME_UNKNOWN": ("intent_id",),
        "BROKER_REJECTED": ("intent_id",),
        "PUBLIC_MARKET_DATA_UNKNOWN": ("error_class",),
        "AUTHENTICATED_DERIV_SESSION_UNKNOWN": ("error_class",),
        "AUTHENTICATED_DERIV_SESSION_VERIFIED": ("environment", "currency"),
        "CONTINUOUS_RUNTIME_UNKNOWN": ("error_class",),
    }.get(event_type, tuple(payload.keys()))
    parts = [f"{key}={payload[key]}" for key in ordered_keys if key in payload]
    text_value = "; ".join(parts) if parts else "No additional details."
    return text_value[:900]
