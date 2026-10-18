from __future__ import annotations
import hashlib, json, os, re, sys, threading, time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

E164 = re.compile(r"^\+[1-9]\d{7,14}$")
ALLOWED = frozenset({"RUNTIME_STARTUP","PUBLIC_MARKET_DATA_UNKNOWN","AUTHENTICATED_DERIV_SESSION_VERIFIED","AUTHENTICATED_DERIV_SESSION_UNKNOWN","WATCHDOG_PROTECT","CONTINUOUS_RUNTIME_UNKNOWN","AUTONOMOUS_RUNTIME_STARTED","KILL_SWITCH_ACTIVATED","KILL_SWITCH_CLEAR_BLOCKED","BROKER_SUBMISSION_EXCEPTION","BROKER_OUTCOME_UNKNOWN","BROKER_ACCEPTED","BROKER_REJECTED","CONTRACT_SETTLED","RECONCILIATION"})

@dataclass(frozen=True)
class MetaWhatsAppConfig:
    enabled: bool
    token: str
    phone_id: str
    recipient: str
    template: str
    language: str
    version: str
    timeout: float
    dedupe_seconds: float
    errors: tuple[str, ...]
    @property
    def ready(self): return self.enabled and not self.errors
    @classmethod
    def from_env(cls):
        enabled=os.getenv("AURELIA_WHATSAPP_ALERTS","false").lower()=="true"
        token=os.getenv("META_WHATSAPP_ACCESS_TOKEN","").strip()
        phone_id=os.getenv("META_WHATSAPP_PHONE_NUMBER_ID","").strip()
        recipient=os.getenv("META_WHATSAPP_TO","").strip()
        template=os.getenv("META_WHATSAPP_TEMPLATE_NAME","").strip()
        language=os.getenv("META_WHATSAPP_TEMPLATE_LANGUAGE","en_US").strip()
        version=os.getenv("META_WHATSAPP_API_VERSION","").strip()
        try: timeout=max(2.0,min(15.0,float(os.getenv("META_WHATSAPP_HTTP_TIMEOUT_SECONDS","8"))))
        except ValueError: timeout=8.0
        try: dedupe=max(30.0,min(3600.0,float(os.getenv("AURELIA_WHATSAPP_DEDUPE_SECONDS","300"))))
        except ValueError: dedupe=300.0
        errors=[]
        if enabled:
            if not token: errors.append("META_WHATSAPP_ACCESS_TOKEN_MISSING")
            if not re.fullmatch(r"\d{5,30}",phone_id): errors.append("META_WHATSAPP_PHONE_NUMBER_ID_MISSING_OR_INVALID")
            if not E164.fullmatch(recipient): errors.append("META_WHATSAPP_TO_MISSING_OR_INVALID")
            if not re.fullmatch(r"[a-z0-9_]{1,512}",template): errors.append("META_WHATSAPP_TEMPLATE_NAME_MISSING_OR_INVALID")
            if not re.fullmatch(r"[A-Za-z0-9_]{2,20}",language): errors.append("META_WHATSAPP_TEMPLATE_LANGUAGE_MISSING_OR_INVALID")
            if not re.fullmatch(r"v\d+\.\d+",version): errors.append("META_WHATSAPP_API_VERSION_MISSING_OR_INVALID")
        return cls(enabled,token,phone_id,recipient,template,language,version,timeout,dedupe,tuple(errors))

class MetaWhatsAppAlertSink:
    def __init__(self,config=None):
        self.config=config or MetaWhatsAppConfig.from_env()
        self._lock=threading.Lock(); self._seen={}
    @classmethod
    def from_env(cls): return cls(MetaWhatsAppConfig.from_env())
    def status(self):
        c=self.config
        return {"provider":"meta","enabled":c.enabled,"ready":c.ready,"configuration_errors":list(c.errors),"recipient_configured":bool(c.recipient),"sender_configured":bool(c.phone_id),"template_configured":bool(c.template)}
    def emit(self,event_type,payload=None):
        payload=payload if isinstance(payload,dict) else {}
        if event_type not in ALLOWED or not self.config.ready or (event_type=="RECONCILIATION" and payload.get("healthy")): return
        key=hashlib.sha256(json.dumps([event_type,_safe(payload)],sort_keys=True,default=str).encode()).hexdigest()
        now=time.monotonic()
        with self._lock:
            self._seen={k:t for k,t in self._seen.items() if now-t<=self.config.dedupe_seconds}
            if key in self._seen: return
            self._seen[key]=now
        threading.Thread(target=self._background,args=(event_type,payload),daemon=True,name="aurelia-meta-whatsapp").start()
    def send_now(self,event_type,payload=None):
        c=self.config; payload=payload if isinstance(payload,dict) else {}
        if not c.enabled: return {"status":"DISABLED"}
        if not c.ready: return {"status":"NOT_CONFIGURED","errors":list(c.errors)}
        if event_type not in ALLOWED: return {"status":"IGNORED_EVENT"}
        if event_type=="RECONCILIATION" and payload.get("healthy"): return {"status":"FILTERED"}
        return self._send(event_type,payload)
    def _background(self,event_type,payload):
        try: self._send(event_type,payload)
        except Exception as exc: print(f"AURELIA_META_WHATSAPP_FAILED:{type(exc).__name__}",file=sys.stderr)
    def _send(self,event_type,payload):
        c=self.config
        params=[{"type":"text","text":event_type[:256]},{"type":"text","text":_summary(event_type,payload)[:900]}]
        body={"messaging_product":"whatsapp","recipient_type":"individual","to":c.recipient.lstrip("+"),"type":"template","template":{"name":c.template,"language":{"code":c.language},"components":[{"type":"body","parameters":params}]}}
        req=Request(f"https://graph.facebook.com/{c.version}/{c.phone_id}/messages",data=json.dumps(body,separators=(",",":")).encode(),headers={"Authorization":f"Bearer {c.token}","Content-Type":"application/json","Accept":"application/json"},method="POST")
        try:
            with urlopen(req,timeout=c.timeout) as resp: result=json.loads(resp.read().decode())
        except HTTPError as exc: raise RuntimeError(f"META_WHATSAPP_HTTP_{exc.code}") from None
        except (URLError,TimeoutError,OSError) as exc: raise RuntimeError(f"META_WHATSAPP_TRANSPORT_{type(exc).__name__}") from None
        except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise RuntimeError(f"META_WHATSAPP_RESPONSE_INVALID_{type(exc).__name__}") from None
        messages=result.get("messages") or []
        if not messages or not messages[0].get("id"): raise RuntimeError("META_WHATSAPP_ACCEPTANCE_ID_MISSING")
        return {"status":"SENT","message_id":str(messages[0]["id"]),"provider_status":"accepted"}

def _safe(payload):
    sensitive=("token","secret","password","credential","authorization","phone")
    return {str(k):v for k,v in payload.items() if not any(s in str(k).lower() for s in sensitive) and (isinstance(v,(str,int,float,bool)) or v is None)}
def _summary(event_type,payload):
    p=_safe(payload)
    keys={"BROKER_ACCEPTED":("symbol","direction","stake","contract_id","decision_id"),"CONTRACT_SETTLED":("symbol","direction","stake","net_delta","post_balance","contract_id"),"RECONCILIATION":("healthy","difference","reason"),"RUNTIME_STARTUP":("runtime_version","live_execution","LIVE_EXECUTION","capital_plane_mode"),"KILL_SWITCH_ACTIVATED":("reason",),"KILL_SWITCH_CLEAR_BLOCKED":("reason",),"WATCHDOG_PROTECT":("reason",),"BROKER_REJECTED":("intent_id",),"BROKER_OUTCOME_UNKNOWN":("intent_id",),"BROKER_SUBMISSION_EXCEPTION":("intent_id","error_class"),"PUBLIC_MARKET_DATA_UNKNOWN":("error_class",),"AUTHENTICATED_DERIV_SESSION_UNKNOWN":("error_class",),"CONTINUOUS_RUNTIME_UNKNOWN":("error_class",),"AUTHENTICATED_DERIV_SESSION_VERIFIED":("environment","currency"),"AUTONOMOUS_RUNTIME_STARTED":("environment","currency","symbol_count")}.get(event_type,())
    return ("; ".join(f"{k}={p[k]}" for k in keys if k in p) or "No additional details.")[:900]
