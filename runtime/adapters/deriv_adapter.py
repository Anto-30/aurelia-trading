from __future__ import annotations
import json,os,time
from datetime import datetime,timezone
from typing import Any,AsyncIterator
from runtime.core.circuit import CircuitBreaker
from runtime.core.events import sha256
from runtime.core.models import AccountIdentity,BrokerOutcome,BrokerResult,CapitalSnapshot,MarketTick
try:
 from websockets.asyncio.client import ClientConnection,connect
except ImportError:
 ClientConnection=Any; connect=None
class DerivProtocolError(RuntimeError): pass
class DerivAdapter:
 def __init__(self,*,ws_url=None,auth_token=None,expected_loginid=None,expected_currency="USD",environment="real",timeout_seconds=10.0):
  self.ws_url=ws_url or os.getenv("DERIV_WS_URL",""); self.auth_token=auth_token if auth_token is not None else os.getenv("DERIV_AUTH_TOKEN",""); self.expected_loginid=expected_loginid or os.getenv("DERIV_EXPECTED_LOGINID",""); self.expected_currency=expected_currency; self.environment=environment; self.timeout_seconds=timeout_seconds; self.ws=None; self._req_id=0; self.last_message_at=0.0; self.authorized=False; self.account=None; self.circuit=CircuitBreaker()
 async def connect(self):
  if connect is None: raise RuntimeError("WEBSOCKETS_DEPENDENCY_MISSING")
  if not self.ws_url: raise DerivProtocolError("DERIV_WS_URL_MISSING")
  self.ws=await connect(self.ws_url,ping_interval=20,ping_timeout=20,close_timeout=5,max_size=2000000); self.last_message_at=time.time()
  reply=await self.request({"authorize":self.auth_token}) if self.auth_token else await self.request({"account":1})
  auth=reply.get("authorize") or reply.get("account") or {}; loginid=str(auth.get("loginid") or auth.get("login_id") or ""); currency=str(auth.get("currency") or ""); at=str(auth.get("account_type") or ("demo" if auth.get("is_virtual") else "real")); at="demo" if at=="virtual" else at
  if not loginid: raise DerivProtocolError("ACCOUNT_IDENTITY_UNVERIFIED")
  if self.expected_loginid and loginid!=self.expected_loginid: raise DerivProtocolError("ACCOUNT_IDENTITY_MISMATCH")
  if currency and currency!=self.expected_currency: raise DerivProtocolError("CURRENCY_MISMATCH")
  self.account=AccountIdentity(loginid,at,currency or self.expected_currency,self.environment); self.authorized=bool(self.auth_token or loginid); self.circuit.record_success(); return self.account
 async def request(self,payload):
  if self.ws is None: raise DerivProtocolError("BROKER_SESSION_NOT_CONNECTED")
  self._req_id+=1; rid=self._req_id; body=dict(payload); body["req_id"]=rid
  try:
   await self.ws.send(json.dumps(body))
   while True:
    raw=await self.ws.recv(); self.last_message_at=time.time(); msg=json.loads(raw)
    if msg.get("req_id") not in (None,rid): continue
    if "error" in msg: raise DerivProtocolError(str(msg["error"]))
    return msg
  except Exception: self.circuit.record_failure(); raise
 async def get_balance(self):
  if not self.account: raise DerivProtocolError("ACCOUNT_NOT_VERIFIED")
  r=await self.request({"balance":1}); x=r.get("balance") or {}; amount=float(x["balance"]); cur=str(x.get("currency") or self.account.currency)
  return CapitalSnapshot(amount,cur,amount,datetime.now(timezone.utc),"deriv:balance",self.account)
 async def active_symbols(self): return list((await self.request({"active_symbols":"brief"})).get("active_symbols") or [])
 async def subscribe_ticks(self,symbol)->AsyncIterator[MarketTick]:
  if self.ws is None: raise DerivProtocolError("BROKER_SESSION_NOT_CONNECTED")
  self._req_id+=1; await self.ws.send(json.dumps({"ticks":symbol,"subscribe":1,"req_id":self._req_id}))
  while True:
   raw=await self.ws.recv(); self.last_message_at=time.time(); msg=json.loads(raw)
   if msg.get("error"): raise DerivProtocolError(str(msg["error"]))
   t=msg.get("tick")
   if t: yield MarketTick(str(t.get("symbol") or symbol),float(t["quote"]),int(t["epoch"]),datetime.now(timezone.utc))
 async def submit_authorized_order(self,payload):
  if not self.authorized: raise DerivProtocolError("BROKER_SESSION_NOT_AUTHORIZED")
  if not self.circuit.permit_new_submission(): raise DerivProtocolError("BROKER_CIRCUIT_OPEN")
  pid=payload.get("proposal_id")
  if not pid: raise DerivProtocolError("ORDER_REQUIRES_BROKER_PROPOSAL_ID")
  try: reply=await self.request({"buy":int(pid),"price":payload["stake"]})
  except Exception: return BrokerResult(BrokerOutcome.UNKNOWN,f"req:{self._req_id}",raw_class="SUBMISSION_RESPONSE_UNKNOWN")
  b=reply.get("buy") or {}; tx=str(b.get("transaction_id") or "") or None; cid=str(b.get("contract_id") or "") or None
  if not tx and not cid: return BrokerResult(BrokerOutcome.UNKNOWN,f"req:{self._req_id}",raw_class="BROKER_ACCEPTANCE_UNRESOLVED")
  return BrokerResult(BrokerOutcome.ACCEPTED,f"req:{self._req_id}",tx,cid,"BUY_ACCEPTED",datetime.now(timezone.utc))
 async def get_contract_status(self,contract_id): return dict((await self.request({"proposal_open_contract":1,"contract_id":int(contract_id)})).get("proposal_open_contract") or {})
 async def close(self):
  if self.ws is not None: await self.ws.close()
  self.ws=None; self.authorized=False; self.account=None
 @property
 def connection_fingerprint(self): return sha256({"ws_url":self.ws_url,"expected_loginid":self.expected_loginid,"currency":self.expected_currency,"environment":self.environment})
