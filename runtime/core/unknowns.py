from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class UnknownCondition:
    code:str
    detail:str
    capital_critical:bool=True

class UnknownRegistry:
    def __init__(self): self._conditions:dict[str,UnknownCondition]={}
    def add(self,condition:UnknownCondition)->None: self._conditions[condition.code]=condition
    def resolve(self,code:str)->None: self._conditions.pop(code,None)
    def any_capital_critical(self)->bool: return any(c.capital_critical for c in self._conditions.values())
    def codes(self)->tuple[str,...]: return tuple(sorted(self._conditions))
