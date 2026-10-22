#!/usr/bin/env python3
"""Frozen, research-only MSNR simulator. Fail-closed on economics and data gaps."""
import argparse, gc, hashlib, json, math, random
from pathlib import Path
import numpy as np
import pandas as pd
SEED=42
np.random.seed(SEED); random.seed(SEED)
REQ=("epoch","open","high","low","close")

def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""): h.update(b)
 return h.hexdigest()

def load_specs(path):
 s=json.loads(Path(path).read_text())
 missing=[k for k in ("pip_size","multiplier","spread_pips","slippage_bps","account_risk_pct","initial_equity") if s.get(k) is None]
 if missing or not s.get("independently_verified",False): raise ValueError("UNVERIFIED INSTRUMENT ECONOMICS; missing/unverified: "+", ".join(missing or ["independently_verified"]))
 if s.get("contract_type") not in ("linear_cfd","linear_multiplier"): raise ValueError("Only linear PnL contracts permitted; binary options forbidden")
 if not 0 < float(s["account_risk_pct"]) <= .01: raise ValueError("Risk must be >0 and <=1%")
 return s

def features(df):
 x=df.copy(); prev=x.close.shift(1)
 tr=pd.concat([(x.high-x.low).abs(),(x.high-prev).abs(),(x.low-prev).abs()],axis=1).max(axis=1)
 x["atr"]=tr.rolling(14,min_periods=14).mean()
 x["ma200"]=x.close.rolling(200,min_periods=200).mean()
 x["prior_low"]=x.low.rolling(20,min_periods=20).min().shift(1)
 x["prior_high"]=x.high.rolling(20,min_periods=20).max().shift(1)
 x["long_signal"]=((x.low<x.prior_low)&(x.close>x.prior_low)&(x.close>x.ma200)).fillna(False)
 x["short_signal"]=((x.high>x.prior_high)&(x.close<x.prior_high)&(x.close<x.ma200)).fillna(False)
 x["regime"]=np.select([x.close>x.ma200,x.close<x.ma200],["trend_up","trend_down"],default="chop")
 return x

def run(a):
 data=Path(a.data); specs=load_specs(a.specs); data_hash=sha(data)
 s=specs; mult=float(s["multiplier"]); pip=float(s["pip_size"]); spread=float(s["spread_pips"])*pip; slip_bps=float(s["slippage_bps"])/10000
 equity=float(s["initial_equity"]); initial=equity; risk_pct=float(s["account_risk_pct"]); pos=None; last_bar=None; pos=None
 ledger=Path(a.ledger); ledger.parent.mkdir(parents=True,exist_ok=True); ledger.write_text("")
 gp=gl=sumr=0.; n=wins=losses=0; cursor=pd.Timestamp(a.start,tz="UTC"); end=pd.Timestamp(a.end,tz="UTC")
 while cursor<end:
  nxt=min(cursor+pd.DateOffset(months=3),end); lo=int((cursor-pd.Timedelta(minutes=250)).timestamp()); hi=int(nxt.timestamp()); pieces=[]
  for part in pd.read_csv(data,chunksize=100000):
   if any(k not in part.columns for k in REQ): raise ValueError("CSV missing required OHLC fields")
   part=part[(part.epoch>=lo)&(part.epoch<hi)]
   if not part.empty: pieces.append(part.copy())
   del part
  if not pieces: raise ValueError(f"No rows in chunk {cursor}..{nxt}")
  df=pd.concat(pieces,ignore_index=True); del pieces; df=df.drop_duplicates("epoch").sort_values("epoch")
  if df[list(REQ)].isna().any().any(): raise ValueError("Null OHLC values; ffill forbidden")
  if (df.epoch.diff().dropna()>120).any(): raise ValueError("Gap >120 seconds; inspect data before simulation")
  df["time"]=pd.to_datetime(df.epoch,unit="s",utc=True); x=features(df).reset_index(drop=True)
  lo_i=int(x.time.searchsorted(cursor)); hi_i=int(x.time.searchsorted(nxt))
  for i in range(max(1,lo_i),hi_i):
   bar=x.iloc[i]; prev=x.iloc[i-1]
   if pos:
    exitp=None; reason=None
    if pos["side"]==1:
     if bar.low<=pos["stop"]: exitp=pos["stop"]; reason="stop"
     elif bar.high>=pos["target"]: exitp=pos["target"]; reason="target"
    else:
     if bar.high>=pos["stop"]: exitp=pos["stop"]; reason="stop"
     elif bar.low<=pos["target"]: exitp=pos["target"]; reason="target"
    if exitp is not None:
     ex_slip=exitp*slip_bps; pnl_exit=(exitp-pos["entry"])*pos["side"]*pos["size"]*mult-((spread/2)+ex_slip)*pos["size"]*mult
     pnl=pnl_exit-pos["entry_cost"]; r=pnl/pos["risk_cash"] if pos["risk_cash"] else 0; equity+=pnl_exit; n+=1; sumr+=r
     if pnl>0: gp+=pnl; wins+=1
     elif pnl<0: gl+=abs(pnl); losses+=1
     with ledger.open("a") as f: f.write(json.dumps({"entry_epoch":pos["entry_epoch"],"exit_epoch":int(bar.epoch),"side":"long" if pos["side"]==1 else "short","entry_price":pos["entry"],"exit_price":float(exitp),"size":pos["size"],"pnl_net":pnl,"entry_spread_cost":pos["entry_cost"],"r_net":r,"exit_reason":reason,"equity_after":equity})+"\n")
     pos=None
   if pos is None and prev.regime!="chop" and pd.notna(prev.atr) and prev.atr>0:
    side=1 if bool(prev.long_signal) else -1 if bool(prev.short_signal) else 0
    if side and ((side==1 and prev.regime=="trend_up") or (side==-1 and prev.regime=="trend_down")):
     raw=float(bar.open); av=float(prev.atr); risk_cash=equity*risk_pct; size=risk_cash/(av*mult)
     if not math.isfinite(size) or size<=0: continue
     entry=raw+side*raw*slip_bps; stop=entry-side*1.5*av; target=entry+side*2*av
     equity-=(spread/2)*size*mult # spread charged at entry, slippage reflected in fill
     pos={"side":side,"entry":entry,"stop":stop,"target":target,"size":size,"risk_cash":risk_cash,"entry_epoch":int(bar.epoch),"entry_cost":(spread/2)*size*mult}
  del x,df; gc.collect(); cursor=nxt
 if pos is not None and last_bar is not None:
  exitp=float(last_bar.close); ex_slip=exitp*slip_bps
  pnl_exit=(exitp-pos["entry"])*pos["side"]*pos["size"]*mult-((spread/2)+ex_slip)*pos["size"]*mult
  pnl=pnl_exit-pos["entry_cost"]; r=pnl/pos["risk_cash"] if pos["risk_cash"] else 0; equity+=pnl_exit; n+=1; sumr+=r
  if pnl>0: gp+=pnl; wins+=1
  elif pnl<0: gl+=abs(pnl); losses+=1
  with ledger.open("a") as f: f.write(json.dumps({"entry_epoch":pos["entry_epoch"],"exit_epoch":int(last_bar.epoch),"side":"long" if pos["side"]==1 else "short","entry_price":pos["entry"],"exit_price":exitp,"size":pos["size"],"pnl_net":pnl,"entry_spread_cost":pos["entry_cost"],"r_net":r,"exit_reason":"end_of_test","equity_after":equity})+"\n")
 pf=gp/gl if gl else (float("inf") if gp else 0.)
 pf_display=pf if math.isfinite(pf) else "Infinity"
 metrics={"trades":n,"wins":wins,"losses":losses,"profit_factor":pf_display,"net_expectancy_R":sumr/n if n else None,"net_pnl":equity-initial,"ending_equity":equity,"seed":SEED,"data_sha256":data_hash,"git_commit_sha":a.commit_sha,"status":"EMPIRICAL_RESULT" if n else "NO_TRADES"}
 print(json.dumps(metrics,indent=2,allow_nan=False))
 if n and ((math.isfinite(pf) and pf<1.15) or metrics["net_expectancy_R"]<=0): print("KILL CRITERIA MET: Baseline alpha insufficient. Halting HMM integration.")
 return metrics

if __name__=="__main__":
 p=argparse.ArgumentParser(); p.add_argument("--data",required=True); p.add_argument("--specs",default="research/msnr_baseline/config/instrument_specs.json"); p.add_argument("--ledger",default="evidence/trade_ledger.jsonl"); p.add_argument("--start",default="2022-10-21"); p.add_argument("--end",default="2024-10-21"); p.add_argument("--commit-sha",required=True); run(p.parse_args())
