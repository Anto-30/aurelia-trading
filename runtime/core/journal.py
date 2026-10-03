from __future__ import annotations
import json
from pathlib import Path
from threading import Lock
class AppendOnlyJournal:
 def __init__(self,path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._lock=Lock()
 def append(self,event):
  with self._lock,self.path.open("a",encoding="utf-8") as f: f.write(json.dumps(event,sort_keys=True,default=str,allow_nan=False)+"\n"); f.flush()
 def read_all(self):
  if not self.path.exists(): return []
  with self.path.open(encoding="utf-8") as f: return [json.loads(x) for x in f if x.strip()]
