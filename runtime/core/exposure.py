from dataclasses import dataclass
from math import isfinite
@dataclass(frozen=True)
class ExposureSnapshot:
 existing:float;pending:float;concurrent_intents:float;correlated:float;new_order:float;hard_limit:float
 def within_limit(self):
  v=(self.existing,self.pending,self.concurrent_intents,self.correlated,self.new_order,self.hard_limit)
  return all(isfinite(x) and x>=0 for x in v) and sum(v[:5])<=self.hard_limit
