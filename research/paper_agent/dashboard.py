"""Read-only localhost dashboard for AURELIA paper decisions.

This dashboard exposes no trading endpoints and does not render unverified PnL
or treat a paper intent as an open position. Keep it bound to loopback; do not
put it behind a public reverse proxy without separate authentication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from math import isfinite
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from .report import build_nightly_report, read_events_readonly


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_events_hash_chain(events: Sequence[Mapping[str, Any]]) -> bool:
    previous = "GENESIS"
    for expected_sequence, event in enumerate(events, start=1):
        try:
            sequence = int(event["sequence"])
            payload_json = str(event["payload_json"])
            payload_hash = _sha256(payload_json)
            if sequence != expected_sequence or payload_hash != event["payload_sha256"]:
                return False
            if event["previous_hash"] != previous:
                return False
            body = {
                "sequence": sequence,
                "event_id": event["event_id"],
                "occurred_at_utc": event["occurred_at_utc"],
                "event_type": event["event_type"],
                "payload_sha256": payload_hash,
                "previous_hash": previous,
            }
            calculated = _sha256(_canonical(body))
            if calculated != event["event_hash"]:
                return False
            previous = calculated
        except (KeyError, TypeError, ValueError, OverflowError):
            return False
    return True


def _safe_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(str(event.get("payload_json", "{}")))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    # Deliberately expose a whitelist, not raw event payloads.
    result: dict[str, Any] = {}
    for key in ("status", "reason", "reasons", "kill_switch_tripped", "allowed_by_risk_gate", "triggering_event_id"):
        value = payload.get(key)
        if isinstance(value, (str, bool, int)):
            result[key] = value
        elif isinstance(value, float) and isfinite(value):
            result[key] = value
        elif isinstance(value, list):
            result[key] = [str(item)[:160] for item in value[:20]]
    decision = payload.get("decision")
    if isinstance(decision, dict):
        result["decision"] = {
            key: decision.get(key)
            for key in ("regime", "direction", "setup_quality", "risk_state", "confidence", "position_size_pct")
            if key in decision
        }
    return result


def build_dashboard_snapshot(
    events: Sequence[Mapping[str, Any]],
    *,
    generated_at_utc: datetime | None = None,
) -> dict[str, Any]:
    now = generated_at_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("DASHBOARD_TIMEZONE_REQUIRED")
    now = now.astimezone(timezone.utc)
    integrity = verify_events_hash_chain(events)

    last_control: Mapping[str, Any] | None = None
    for event in events:
        if event.get("event_type") in {"KILL_SWITCH_TRIPPED", "KILL_SWITCH_RESET"}:
            last_control = event
    if not integrity:
        kill_switch_state = "BLOCKED_LEDGER_INTEGRITY_INVALID"
    elif last_control is None:
        kill_switch_state = "ARMED_NOT_TRIPPED"
    elif last_control.get("event_type") == "KILL_SWITCH_TRIPPED":
        kill_switch_state = "LATCHED"
    else:
        kill_switch_state = "ARMED_NOT_TRIPPED"

    report = build_nightly_report(events, generated_at_utc=now)
    decisions = [
        {
            "event_id": str(event.get("event_id", ""))[:100],
            "occurred_at_utc": str(event.get("occurred_at_utc", ""))[:40],
            "event_type": str(event.get("event_type", "UNKNOWN"))[:40],
            **_safe_payload(event),
        }
        for event in events
        if event.get("event_type") in {
            "PAPER_INTENT", "MISSED_SIGNAL", "DECISION_EVALUATED", "KILL_SWITCH_TRIPPED", "KILL_SWITCH_RESET"
        }
    ][-20:]
    decisions.reverse()

    return {
        "schema": "aurelia.paper_agent.dashboard.v1",
        "generated_at_utc": now.isoformat(),
        "system_status": "HEALTHY_RESEARCH_ONLY" if integrity else "BLOCKED_LEDGER_INTEGRITY_INVALID",
        "ledger_integrity": "VALID" if integrity else "INVALID",
        "event_count_total": len(events),
        "event_counts_24h": report["event_counts_24h"],
        "paper_intents_24h": report["event_counts_24h"].get("PAPER_INTENT", 0),
        "missed_signals_24h": report["event_counts_24h"].get("MISSED_SIGNAL", 0),
        "kill_switch_state": kill_switch_state,
        "pnl": None,
        "win_rate": None,
        "open_positions": [],
        "performance_metrics_status": "UNAVAILABLE_NO_VERIFIED_SETTLED_PAPER_OUTCOMES",
        "paper_intents_are_not_fills": True,
        "capital_authority": False,
        "order_submission_permitted": False,
        "live_execution_authorized": False,
        "recent_events": decisions,
    }


class _DashboardHandler(BaseHTTPRequestHandler):
    server_version = "AURELIA-PaperDashboard/1.0"

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        database_path = self.server.database_path  # type: ignore[attr-defined]
        if route == "/healthz":
            self._send(200, "application/json; charset=utf-8", b'{"status":"ok","live_execution_authorized":false}')
            return
        if route == "/api/status":
            try:
                events = read_events_readonly(database_path)
                snapshot = build_dashboard_snapshot(events)
                status = 200 if snapshot["ledger_integrity"] == "VALID" else 503
                body = json.dumps(snapshot, sort_keys=True, allow_nan=False).encode("utf-8")
                self._send(status, "application/json; charset=utf-8", body)
            except (OSError, ValueError, RuntimeError) as exc:
                body = json.dumps({
                    "system_status": "BLOCKED",
                    "reason": type(exc).__name__,
                    "live_execution_authorized": False,
                }).encode("utf-8")
                self._send(503, "application/json; charset=utf-8", body)
            return
        if route == "/":
            page = b"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AURELIA Paper Decision Dashboard</title>
<style>
:root{color-scheme:dark;background:#111827;color:#f3f4f6;font:16px system-ui,sans-serif}
body{max-width:1100px;margin:0 auto;padding:18px}
h1{font-size:1.45rem;margin-bottom:6px}.sub{color:#cbd5e1;margin-top:0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
.card{padding:14px;border:1px solid #475569;border-radius:10px;background:#1f2937}
.label{font-size:.82rem;color:#cbd5e1}.value{font-size:1.2rem;font-weight:650;margin-top:8px;overflow-wrap:anywhere}
.warning{padding:12px;border-left:4px solid #f59e0b;background:#292524;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:.88rem}th,td{text-align:left;padding:8px;border-bottom:1px solid #475569;vertical-align:top}
.wrap{overflow-x:auto}code{overflow-wrap:anywhere}#err{color:#fca5a5}
</style></head>
<body><h1>AURELIA · Paper Decision Dashboard</h1>
<p class="sub">Read-only local monitor · refreshes every 5 seconds</p>
<div class="warning">Research mode only. This surface cannot submit orders. Paper intents are not fills; PnL, win rate and open positions remain unavailable until a verified paper contract lifecycle exists.</div>
<div id="err"></div><div class="grid" id="cards"></div>
<h2>Recent dispositions</h2><div class="wrap"><table><thead><tr><th>Time (UTC)</th><th>Event</th><th>Decision</th><th>Disposition / reason</th></tr></thead><tbody id="events"></tbody></table></div>
<p class="sub" id="updated">Waiting for ledger…</p>
<script>
const displayText = v => v === null || v === undefined ? "UNAVAILABLE" : String(v);
function card(label,value){const box=document.createElement("div");box.className="card";const l=document.createElement("div");l.className="label";l.textContent=label;const v=document.createElement("div");v.className="value";v.textContent=displayText(value);box.append(l,v);return box;}
async function refresh(){
 try{
  const response=await fetch("/api/status",{cache:"no-store"});
  const data=await response.json();
  document.getElementById("err").textContent=response.ok?"":"BLOCKED: ledger unavailable or integrity check failed.";
  const cards=document.getElementById("cards");cards.replaceChildren();
  [["System",data.system_status],["Ledger integrity",data.ledger_integrity],["Kill switch",data.kill_switch_state],["Total events",data.event_count_total],["Paper intents (24h)",data.paper_intents_24h],["Missed signals (24h)",data.missed_signals_24h],["PnL",data.pnl],["Win rate",data.win_rate],["Open positions",data.open_positions?.length],["Trading authorization",data.live_execution_authorized]].forEach(x=>cards.append(card(x[0],x[1])));
  const body=document.getElementById("events");body.replaceChildren();
  for(const item of (data.recent_events||[])){
   const tr=document.createElement("tr");
   const decision=item.decision?(String(item.decision.direction||"")+" / "+String(item.decision.regime||"")+" / conf "+displayText(item.decision.confidence)):"—";
   const why=item.reason||((item.reasons||[]).join(", "))||displayText(item.status);
   [item.occurred_at_utc,item.event_type,decision,why].forEach(value=>{const td=document.createElement("td");td.textContent=displayText(value);tr.append(td);});
   body.append(tr);
  }
  document.getElementById("updated").textContent="Updated "+displayText(data.generated_at_utc)+" · metrics: "+displayText(data.performance_metrics_status);
 }catch(e){document.getElementById("err").textContent="Unable to read paper ledger. No trading action is available.";}
}
refresh();setInterval(refresh,5000);
</script></body></html>"""
            self._send(200, "text/html; charset=utf-8", page)
            return
        self._send(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self) -> None:
        self._send(405, "text/plain; charset=utf-8", b"read-only dashboard")

    def log_message(self, format: str, *args: Any) -> None:
        return


class PaperDashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve_dashboard(database_path: str | Path, *, host: str = "127.0.0.1", port: int = 8765) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("DASHBOARD_MUST_BIND_TO_LOOPBACK")
    target = str(Path(database_path).expanduser().resolve())
    events = read_events_readonly(target)
    if not verify_events_hash_chain(events):
        raise RuntimeError("PAPER_LEDGER_INTEGRITY_INVALID")
    server = PaperDashboardServer((host, port), _DashboardHandler)
    server.database_path = target  # type: ignore[attr-defined]
    try:
        print(f"AURELIA read-only paper dashboard: http://{host}:{port}")
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Existing SQLite paper-event ledger")
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in [1, 65535]")
    serve_dashboard(args.db, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
