#!/usr/bin/env python3
"""Verify candle CSV structure, hashes, OHLC consistency, and gaps >120s."""
import argparse,csv,hashlib,json,math
from pathlib import Path
FIELDS=("epoch","open","high","low","close")
def digest(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""): h.update(b)
 return h.hexdigest()
def verify(name):
 p=Path(name); mp=Path(str(p)+".manifest.json")
 if not p.is_file() or not mp.is_file(): raise ValueError("CSV or manifest missing")
 m=json.loads(mp.read_text()); actual=digest(p)
 if actual!=m.get("sha256"): raise ValueError("SHA-256 manifest mismatch")
 n=0; prev=None; gaps=[]
 with p.open(newline="") as f:
  r=csv.DictReader(f)
  if tuple(r.fieldnames or ())!=FIELDS: raise ValueError(f"Unexpected fields {r.fieldnames}")
  for row in r:
   t=int(row["epoch"]); v={k:float(row[k]) for k in FIELDS[1:]}
   if not all(math.isfinite(z) for z in v.values()): raise ValueError("Non-finite OHLC")
   if v["high"]<max(v["open"],v["close"],v["low"]) or v["low"]>min(v["open"],v["close"],v["high"]): raise ValueError("Invalid OHLC")
   if prev is not None:
    if t<=prev: raise ValueError("Duplicate/unsorted epochs")
    if t-prev>120: gaps.append({"from":prev,"to":t,"seconds":t-prev})
   prev=t; n+=1
 if not n: raise ValueError("Empty CSV")
 if gaps: raise ValueError(f"{len(gaps)} gaps >120 seconds; first gap {gaps[0]}")
 return {"file":str(p),"rows":n,"sha256":actual,"gaps_over_120_seconds":0,"verified":True}
if __name__=="__main__":
 p=argparse.ArgumentParser(); p.add_argument("csv",nargs="+"); a=p.parse_args(); print(json.dumps([verify(x) for x in a.csv],indent=2))
