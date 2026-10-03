from __future__ import annotations
import asyncio,json,os
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.core.health import HealthSnapshot
from runtime.core.models import RuntimeState
from runtime.core.runtime_config import load_config_hash
from runtime.core.state import RuntimeStateMachine
ROOT=Path(__file__).resolve().parents[1]
class HealthHandler(BaseHTTPRequestHandler):
 health=None; state=RuntimeState.BOOT
 def log_message(self,format,*args):return
 def do_GET(self):
  if self.path not in {"/health","/ready"}:self.send_response(404);self.end_headers();return
  h=self.health; ok=True if h is None else (h.liveness() if self.path=="/health" else h.readiness()); body={"status":"STARTING" if h is None else ("HEALTHY" if h.readiness() else "DEGRADED"),"state":self.state.value,"liveness":None if h is None else h.liveness(),"readiness":None if h is None else h.readiness(),"capital_can_open_new_exposure":False if h is None else h.can_open_new_exposure(),"critical_unknowns":[] if h is None else sorted(h.critical_unknowns)}; raw=json.dumps(body).encode(); self.send_response(200 if ok else 503);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
def start_server(port):
 s=ThreadingHTTPServer(("0.0.0.0",port),HealthHandler);Thread(target=s.serve_forever,name="aurelia-health",daemon=True).start();return s
async def main():
 server=start_server(int(os.getenv("PORT","8080")));config_hash=load_config_hash(ROOT);sm=RuntimeStateMachine();sm.transition(RuntimeState.SELF_CHECK);h=HealthSnapshot(datetime.now(timezone.utc));HealthHandler.health=h;HealthHandler.state=sm.state;print(json.dumps({"component":"AURELIA","runtime_version":"0.1.0-baseline-2026-10-03","config_hash":config_hash,"FINAL_EXECUTION_AUTHORIZATION":False,"LIVE_EXECUTION":"BLOCKED","capital_plane_mode":"VERIFY_ONLY"},sort_keys=True));_adapter=DerivAdapter(ws_url=os.getenv("DERIV_WS_URL",""),auth_token=os.getenv("DERIV_AUTH_TOKEN",""),expected_loginid=os.getenv("DERIV_EXPECTED_LOGINID",""),expected_currency=os.getenv("DERIV_CURRENCY","USD"),environment=os.getenv("DERIV_ENVIRONMENT","real"))
 while True:
  h.process_heartbeat=datetime.now(timezone.utc);h.kill_switch_off=False;h.broker_session=False;h.market_data_fresh=False;h.capital_fresh=False;h.reconciliation_healthy=False;HealthHandler.state=RuntimeState.CAPITAL_PROTECTED;await asyncio.sleep(5)
if __name__=="__main__":asyncio.run(main())
