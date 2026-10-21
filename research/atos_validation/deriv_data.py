"""Deriv WebSocket candle-history adapter and inference latency telemetry.

Uses documented Deriv WebSocket API endpoint pattern. API tokens are not needed
for public history requests; never place tokens in source or logs. Deriv candles
do not guarantee exchange-style volume: no synthetic volume is fabricated.
"""
from __future__ import annotations
import json, os, time, threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
import pandas as pd
import websocket

DERIV_WS_BASE="wss://ws.derivws.com/websockets/v3"

@dataclass(frozen=True)
class LatencyRecord:
    tick_received_monotonic: float
    inference_done_monotonic: float
    order_payload_ready_monotonic: float
    inference_ms: float
    end_to_end_ms: float
    alert_over_200ms: bool

class LatencyTelemetry:
    def __init__(self, threshold_ms: float=200.0, logger: Callable[[dict],None]|None=None):
        self.threshold_ms=threshold_ms; self.logger=logger or (lambda x: None)
    def record(self, tick_received: float, inference_done: float, payload_ready: float) -> LatencyRecord:
        inference=(inference_done-tick_received)*1000
        total=(payload_ready-tick_received)*1000
        row=LatencyRecord(tick_received,inference_done,payload_ready,inference,total,total>self.threshold_ms)
        self.logger({"event":"latency","inference_ms":inference,"end_to_end_ms":total,
                     "alert_over_200ms":row.alert_over_200ms})
        return row

class DerivHistoryClient:
    def __init__(self, app_id: str|None=None, timeout_seconds: float=20):
        self.app_id=app_id or os.getenv("DERIV_APP_ID")
        if not self.app_id or not self.app_id.isdigit(): raise ValueError("Set DERIV_APP_ID to a numeric application ID")
        self.url=f"{DERIV_WS_BASE}?app_id={self.app_id}"
        self.timeout=timeout_seconds

    def candles(self, symbol: str, start_epoch: int, end_epoch: int,
                granularity: int=60, count: int=5000) -> pd.DataFrame:
        if not symbol or start_epoch>=end_epoch or granularity not in (60,900) or not 1<=count<=5000:
            raise ValueError("invalid symbol/date range/granularity/count")
        ws=websocket.create_connection(self.url,timeout=self.timeout)
        try:
            req={"ticks_history":symbol,"start":int(start_epoch),"end":int(end_epoch),
                 "style":"candles","granularity":int(granularity),"count":int(count),"adjust_start_time":1}
            ws.send(json.dumps(req))
            deadline=time.monotonic()+self.timeout
            while time.monotonic()<deadline:
                msg=json.loads(ws.recv())
                if msg.get("error"): raise RuntimeError(f"Deriv API error: {msg['error'].get('code','unknown')}: {msg['error'].get('message','')}")
                if msg.get("msg_type")=="candles":
                    candles=msg.get("candles",[])
                    df=pd.DataFrame(candles)
                    if df.empty: raise ValueError("Deriv returned no candles")
                    df["epoch"]=pd.to_numeric(df["epoch"],errors="raise").astype("int64")
                    for col in ("open","high","low","close"):
                        df[col]=pd.to_numeric(df[col],errors="raise")
                    df=df.sort_values("epoch").drop_duplicates("epoch",keep="last")
                    if (df[["open","high","low","close"]]<=0).any().any(): raise ValueError("non-positive price")
                    if (df.high < df[["open","close","low"]].max(axis=1)).any() or (df.low > df[["open","close","high"]].min(axis=1)).any():
                        raise ValueError("invalid OHLC ordering")
                    df["timestamp"]=pd.to_datetime(df.epoch,unit="s",utc=True)
                    # Deriv synthetic-index candles do not supply traded volume. Keep it missing.
                    df["volume"]=float("nan")
                    expected=granularity
                    gaps=df.epoch.diff().dropna()
                    if not gaps.eq(expected).all():
                        raise ValueError(f"history has gaps or irregular spacing: {int((gaps!=expected).sum())} intervals; do not silently fill")
                    return df[["timestamp","epoch","open","high","low","close","volume"]].reset_index(drop=True)
            raise TimeoutError("timed out waiting for Deriv candles")
        finally:
            ws.close()

    def backfill(self, symbol: str, start_epoch: int, end_epoch: int,
                 granularity: int=60, bars_per_request: int=4500) -> pd.DataFrame:
        """Chunk a long historical request and validate the joined timeline.

        This is a bounded sequential backfill, not a guarantee of 12–24 months:
        callers must verify that the symbol existed for the requested interval.
        """
        if granularity not in (60,900) or not 100 <= bars_per_request <= 5000:
            raise ValueError("granularity must be 60/900 seconds and bars_per_request 100..5000")
        if start_epoch >= end_epoch: raise ValueError("start_epoch must precede end_epoch")
        chunk_seconds=(bars_per_request-1)*granularity
        frames=[]; cursor=int(start_epoch)
        while cursor < end_epoch:
            stop=min(cursor+chunk_seconds,int(end_epoch))
            frames.append(self.candles(symbol,cursor,stop,granularity=granularity,count=bars_per_request))
            cursor=stop
        if not frames: raise ValueError("empty requested interval")
        out=pd.concat(frames,ignore_index=True).sort_values("epoch")
        out=out.drop_duplicates("epoch",keep="last").reset_index(drop=True)
        expected=list(range(int(out.epoch.iloc[0]),int(out.epoch.iloc[-1])+1,granularity))
        if out.epoch.astype(int).tolist()!=expected:
            raise ValueError("joined history is not gap-free; reject dataset")
        if int(out.epoch.iloc[0])>start_epoch+granularity or int(out.epoch.iloc[-1])<end_epoch-granularity:
            raise ValueError("returned history does not cover the requested interval")
        return out

def time_call(fn: Callable, *args, **kwargs):
    """Measure local monotonic elapsed time; this does not prove broker receipt/execution."""
    t0=time.monotonic(); result=fn(*args,**kwargs); t1=time.monotonic()
    return result, (t1-t0)*1000
