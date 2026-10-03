from dataclasses import dataclass
@dataclass
class CircuitBreaker:
 failure_threshold:int=3; open:bool=False; failures:int=0
 def record_failure(self): self.failures+=1; self.open=self.failures>=self.failure_threshold; return self.open
 def record_success(self): self.failures=0; self.open=False
 def permit_new_submission(self): return not self.open
