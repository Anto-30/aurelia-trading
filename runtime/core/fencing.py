from dataclasses import dataclass
from threading import Lock
@dataclass(frozen=True)
class FenceToken: generation:int; owner:str
class ExecutionFence:
 def __init__(self): self._generation=0; self._owner=None; self._lock=Lock()
 def acquire(self,owner):
  with self._lock: self._generation+=1; self._owner=owner; return FenceToken(self._generation,owner)
 def valid(self,token):
  with self._lock:return token.generation==self._generation and token.owner==self._owner
 def revoke(self):
  with self._lock:self._generation+=1; self._owner=None; return self._generation
