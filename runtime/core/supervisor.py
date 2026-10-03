from dataclasses import dataclass
from datetime import datetime,timezone
from threading import Event,Thread
@dataclass
class SupervisorMetrics: heartbeats:int=0; protective_transitions:int=0; failures:int=0; last_heartbeat:datetime|None=None
class RuntimeSupervisor:
 def __init__(self,interval_seconds=5.0): self.interval_seconds=interval_seconds; self.metrics=SupervisorMetrics(); self.stop_event=Event(); self._thread=None
 def start(self,heartbeat,protect):
  def loop():
   while not self.stop_event.wait(self.interval_seconds):
    self.metrics.last_heartbeat=datetime.now(timezone.utc); self.metrics.heartbeats+=1
    try: healthy=heartbeat()
    except Exception: healthy=False; self.metrics.failures+=1
    if not healthy: self.metrics.protective_transitions+=1; protect("WATCHDOG_HEALTH_FAILURE")
  self._thread=Thread(target=loop,name="aurelia-watchdog",daemon=True); self._thread.start()
 def stop(self):
  self.stop_event.set()
  if self._thread: self._thread.join(timeout=5)
