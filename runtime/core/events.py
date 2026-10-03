from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
import hashlib,json
from typing import Any
from .models import utc_now

def canonical_json(payload:Any)->str: return json.dumps(payload,sort_keys=True,separators=(",",":"),default=str,allow_nan=False)
def sha256(payload:Any)->str: return hashlib.sha256(canonical_json(payload).encode()).hexdigest()
def event_envelope(*,event_type,event_id,correlation_id,payload,source_hash,config_hash,occurred_at:datetime|None=None):
 body={"schema":"aurelia.event.v1","event_id":event_id,"correlation_id":correlation_id,"event_type":event_type,"occurred_at_utc":(occurred_at or utc_now()).isoformat(),"source_hash":source_hash,"config_hash":config_hash,"payload":payload}; body["record_hash"]=sha256(body); return body
def event_from_dataclass(*,event_type,event_id,correlation_id,value,source_hash,config_hash): return event_envelope(event_type=event_type,event_id=event_id,correlation_id=correlation_id,payload=asdict(value),source_hash=source_hash,config_hash=config_hash)
