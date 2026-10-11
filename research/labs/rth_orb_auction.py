"""Research-only RTH ORB/sweep primitives. No broker/order interface."""
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo
import math

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

@dataclass(frozen=True)
class Bar:
    timestamp: object
    open: float
    high: float
    low: float
    close: float
    volume: float
    complete: bool = True

    def validate(self):
        if getattr(self.timestamp, "tzinfo", None) is None:
            raise ValueError("timestamp must be timezone-aware")
        if not self.complete:
            raise ValueError("incomplete bar")
        values=(self.open,self.high,self.low,self.close,self.volume)
        if any(not math.isfinite(float(v)) for v in values):
            raise ValueError("non-finite OHLCV")
        if self.volume < 0 or self.low > min(self.open,self.close) or self.high < max(self.open,self.close) or self.low > self.high:
            raise ValueError("invalid OHLCV")

@dataclass(frozen=True)
class ContractSpec:
    symbol: str
    tick_size: float
    tick_value: float
    point_value: float

    def validate(self):
        if not self.symbol or any(not math.isfinite(v) or v <= 0 for v in (self.tick_size,self.tick_value,self.point_value)):
            raise ValueError("invalid contract spec")

@dataclass(frozen=True)
class Costs:
    round_trip_fees: float
    slippage_ticks_per_side: float = 1.0
    spread_ticks_round_trip: float = 0.0

    def validate(self):
        if any(not math.isfinite(v) or v < 0 for v in (self.round_trip_fees,self.slippage_ticks_per_side,self.spread_ticks_round_trip)):
            raise ValueError("invalid cost assumptions")

def validate_bars(bars):
    rows=list(bars)
    if not rows:
        raise ValueError("INSUFFICIENT EVIDENCE: no bars")
    for b in rows: b.validate()
    stamps=[b.timestamp.astimezone(UTC) for b in rows]
    if stamps != sorted(stamps) or len(stamps) != len(set(stamps)):
        raise ValueError("timestamps must be unique and ordered")
    return rows

def opening_range(bars, session_date):
    rows=validate_bars(bars)
    selected=[]
    for b in rows:
        t=b.timestamp.astimezone(NY)
        wall=t.time().replace(tzinfo=None)
        if t.date()==session_date and t.weekday()<5 and time(9,30)<=wall<time(9,45):
            selected.append(b)
    if not selected:
        raise ValueError("INSUFFICIENT EVIDENCE: opening range unavailable")
    return max(b.high for b in selected), min(b.low for b in selected)

def orb_close_candidate(bar, or_high, or_low, decision_time, last_entry=time(15,30)):
    bar.validate()
    if decision_time.tzinfo is None:
        return {"strategy":"NO_TRADE","direction":"NONE","reason":"naive decision timestamp"}
    t=decision_time.astimezone(NY)
    if not time(9,45)<=t.time().replace(tzinfo=None)<=last_entry:
        return {"strategy":"NO_TRADE","direction":"NONE","reason":"outside entry window"}
    if bar.timestamp.astimezone(UTC)>decision_time.astimezone(UTC):
        return {"strategy":"NO_TRADE","direction":"NONE","reason":"future bar"}
    if bar.close>or_high:
        return {"strategy":"ORB_CLOSE","direction":"LONG","reference":or_high,"reason":"completed close above OR high"}
    if bar.close<or_low:
        return {"strategy":"ORB_CLOSE","direction":"SHORT","reference":or_low,"reason":"completed close below OR low"}
    return {"strategy":"NO_TRADE","direction":"NONE","reason":"no confirmed close outside range"}

def approximate_profile(bars, tick_size, value_area_fraction=.70):
    """Uniform bar-volume allocation; explicitly not true volume-at-price."""
    rows=validate_bars(bars)
    if not math.isfinite(tick_size) or tick_size<=0 or not 0<value_area_fraction<=1:
        raise ValueError("invalid profile parameters")
    bins={}
    for b in rows:
        lo=round(b.low/tick_size); hi=round(b.high/tick_size)
        n=hi-lo+1
        for k in range(lo,hi+1): bins[k]=bins.get(k,0.0)+b.volume/n
    if not bins or sum(bins.values())<=0: raise ValueError("no usable volume")
    poc=max(sorted(bins),key=lambda k:bins[k])
    target=sum(bins.values())*value_area_fraction
    left=right=poc; vol=bins[poc]
    while vol<target and (left>min(bins) or right<max(bins)):
        lv=bins.get(left-1,-1); rv=bins.get(right+1,-1)
        if rv>lv: right+=1; vol+=bins[right]
        elif left>min(bins): left-=1; vol+=bins[left]
        else: right+=1; vol+=bins[right]
    return {"poc":poc*tick_size,"vah":right*tick_size,"val":left*tick_size,
            "total_volume":sum(bins.values()),"method":"approximate uniform allocation, not true VAP"}

def contracts_for_risk(equity, entry, stop, spec, costs, risk_fraction=.0025):
    spec.validate(); costs.validate()
    if not math.isfinite(equity) or equity<=0 or not 0<risk_fraction<=.005:
        raise ValueError("invalid equity/risk fraction")
    ticks=math.ceil(abs(entry-stop)/spec.tick_size)
    if ticks<1: return 0
    risk=ticks*spec.tick_value+costs.round_trip_fees+(2*costs.slippage_ticks_per_side+costs.spread_ticks_round_trip)*spec.tick_value
    return max(0,math.floor(equity*risk_fraction/risk)) if risk>0 else 0
