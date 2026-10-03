from __future__ import annotations
from dataclasses import dataclass
from threading import Lock
@dataclass(frozen=True)
class IntentRecord: intent_id:str; broker_transaction_id:str|None; economic_effect_count:int
class IdempotencyStore:
 def __init__(self): self._records={}; self._lock=Lock()
 def get(self,i):
  with self._lock:return self._records.get(i)
 def register_intent(self,i):
  with self._lock:
   if i in self._records:return self._records[i]
   self._records[i]=IntentRecord(i,None,0); return self._records[i]
 def attach_broker_transaction(self,i,tx):
  with self._lock:
   c=self._records.get(i)
   if c is None: raise KeyError(i)
   if c.broker_transaction_id and c.broker_transaction_id!=tx: raise RuntimeError("BROKER_TRANSACTION_CONFLICT")
   self._records[i]=IntentRecord(i,tx,c.economic_effect_count); return self._records[i]
 def record_economic_effect(self,i):
  with self._lock:
   c=self._records.get(i)
   if c is None: raise KeyError(i)
   if c.economic_effect_count>=1: raise RuntimeError("DUPLICATE_ECONOMIC_EFFECT")
   self._records[i]=IntentRecord(i,c.broker_transaction_id,1); return self._records[i]
 def economic_effect_count(self,i): c=self.get(i); return 0 if c is None else c.economic_effect_count
