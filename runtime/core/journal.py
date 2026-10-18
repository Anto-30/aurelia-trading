from __future__ import annotations
import json, os
from pathlib import Path
from threading import Lock
from runtime.notifications.whatsapp import WhatsAppAlertSink

class _DisabledAlertSink:
    def emit(self,event_type,payload): return None
    def status(self): return {"enabled":False,"ready":False,"configuration_errors":["ALERT_PROVIDER_DISABLED_OR_INVALID"]}

def _configured_alert_sink():
    provider=os.getenv("AURELIA_WHATSAPP_PROVIDER","twilio").strip().lower()
    if provider=="meta":
        from runtime.notifications.meta_whatsapp import MetaWhatsAppAlertSink
        return MetaWhatsAppAlertSink.from_env()
    if provider=="twilio": return WhatsAppAlertSink.from_env()
    return _DisabledAlertSink()

class AppendOnlyJournal:
    def __init__(self,path,*,alert_sink=None):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._lock=Lock()
        self.alert_sink=alert_sink if alert_sink is not None else _configured_alert_sink()
    def append(self,event):
        with self._lock,self.path.open("a",encoding="utf-8") as f:
            f.write(json.dumps(event,sort_keys=True,default=str,allow_nan=False)+"\n"); f.flush()
        if isinstance(event,dict):
            try: self.alert_sink.emit(str(event.get("event_type","")),event.get("payload") or {})
            except Exception: pass
    def read_all(self):
        if not self.path.exists(): return []
        with self.path.open(encoding="utf-8") as f: return [json.loads(x) for x in f if x.strip()]
