#!/usr/bin/env python3
"""Public-only R_100 candle downloader for Deriv Options API. No credentials."""
import argparse, asyncio, csv, hashlib, json, math
from datetime import datetime, timezone
from pathlib import Path
import websockets

URL="wss://api.derivws.com/trading/v1/options/ws/public"
FIELDS=("epoch","open","high","low","close")
START=int(datetime(2022,10,21,tzinfo=timezone.utc).timestamp())
END=int(datetime(2024,10,21,tzinfo=timezone.utc).timestamp())

def sha(path):
 h=hashlib.sha256()
 with open(path,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""): h.update(b)
 return h.hexdigest()

async def fetch_chunk(start,end,granularity,timeout):
 count=min(5000,(end-start)//granularity+2)
 # ticks_history is the documented history operation; no legacy symbol/loginid parameter.
 payload={"ticks_history":"R_100","start":start,"end":end,"style":"candles","granularity":granularity,"count":count,"req_id":17}
 async with websockets.connect(URL,open_timeout=timeout,close_timeout=5,ping_interval=20,ping_timeout=20,max_size=8_000_000) as ws:
  await ws.send(json.dumps(payload))
  while True:
   msg=json.loads(await asyncio.wait_for(ws.recv(),timeout=timeout))
   if msg.get("error") or msg.get("errors"): raise RuntimeError(f"Deriv API error: {msg.get('error') or msg.get('errors')}")
   if msg.get("req_id") not in (None,17): continue
   candles=msg.get("candles")
   if not isinstance(candles,list): raise ValueError(f"Expected candles list, got keys {list(msg)}")
   out=[]
   for c in candles:
    if not isinstance(c,dict) or any(k not in c for k in FIELDS): raise ValueError(f"Missing required candle field: {c!r}")
    r={"epoch":int(c["epoch"])}
    for k in ("open","high","low","close"):
     r[k]=float(c[k])
     if not math.isfinite(r[k]): raise ValueError(f"Non-finite {k}")
    if r["high"]<max(r["open"],r["close"],r["low"]) or r["low"]>min(r["open"],r["close"],r["high"]): raise ValueError("Invalid OHLC relationship")
    out.append(r)
   return out

async def interval(outdir,gran,start,end,timeout):
 name=f"R_100_{'1m' if gran==60 else '15m'}.csv"; target=outdir/name; tmp=target.with_suffix(".tmp")
 seen=set(); pos=start
 with open(tmp,"w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader()
  while pos<end:
   stop=min(end,pos+3*86400); err=None
   for attempt in range(3):
    try: rows=await fetch_chunk(pos,stop,gran,timeout); break
    except Exception as e:
     err=e
     if attempt==2: raise
     await asyncio.sleep(1.5*(attempt+1))
   for r in sorted(rows,key=lambda z:z["epoch"]):
    if start<=r["epoch"]<=end and r["epoch"] not in seen: w.writerow(r); seen.add(r["epoch"])
   f.flush(); pos=stop
   if pos<end: await asyncio.sleep(1.5)
 tmp.replace(target); ordered=sorted(seen)
 gaps=[{"from_epoch":a,"to_epoch":b,"gap_seconds":b-a} for a,b in zip(ordered,ordered[1:]) if b-a>120]
 report={"file":name,"symbol":"R_100","granularity_seconds":gran,"rows":len(seen),"sha256":sha(target),"gaps_over_120_seconds":len(gaps),"largest_gap_seconds":max([g["gap_seconds"] for g in gaps],default=0),"gap_examples":gaps[:20],"endpoint":URL,"authenticated":False}
 Path(str(target)+".manifest.json").write_text(json.dumps(report,indent=2)+"\n")
 return report

async def main(args):
 out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True); reports=[]
 for g in (60,900): reports.append(await interval(out,g,args.start_epoch,args.end_epoch,args.timeout))
 (out/"manifest.json").write_text(json.dumps({"files":reports,"generated_utc":datetime.now(timezone.utc).isoformat()},indent=2)+"\n")
 print(json.dumps(reports,indent=2))

if __name__=="__main__":
 p=argparse.ArgumentParser(); p.add_argument("--out-dir",default="data/raw"); p.add_argument("--start-epoch",type=int,default=START); p.add_argument("--end-epoch",type=int,default=END); p.add_argument("--timeout",type=float,default=20)
 a=p.parse_args()
 if a.end_epoch<=a.start_epoch: p.error("end epoch must exceed start epoch")
 asyncio.run(main(a))
