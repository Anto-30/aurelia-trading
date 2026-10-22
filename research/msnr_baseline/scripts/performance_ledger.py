#!/usr/bin/env python3
"""Cost raw linear trade records and compute auditable post-cost metrics.

Requires all assumptions on the CLI; never assumes a placeholder commission or
contract multiplier is a verified Deriv value. Only raw trades are accepted so
transaction costs cannot accidentally be charged twice.
"""
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

REQUIRED = ("entry_time", "exit_time", "entry_price", "exit_price", "direction", "size", "initial_risk")
DERIVED = {"gross_pnl", "commission_cost", "spread_cost", "slippage_cost", "transaction_cost", "net_pnl", "r_multiple", "equity_after_trade"}

class LedgerError(ValueError):
    pass

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

class EmpiricalValidationEngine:
    def __init__(self, *, commission_per_unit_round_trip: float, spread_pips_round_trip: float,
                 pip_size_price: float, slippage_bps_per_fill: float, linear_multiplier: float,
                 initial_equity: float):
        values=locals().copy(); values.pop("self")
        for name,value in values.items():
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(float(value)):
                raise LedgerError(f"{name} must be a finite numeric value")
        if commission_per_unit_round_trip<0 or spread_pips_round_trip<0 or slippage_bps_per_fill<0:
            raise LedgerError("Commission, spread and slippage must be non-negative")
        if pip_size_price<=0 or linear_multiplier<=0 or initial_equity<=0:
            raise LedgerError("pip_size_price, multiplier and initial_equity must be positive")
        self.commission=float(commission_per_unit_round_trip); self.spread_pips=float(spread_pips_round_trip)
        self.pip_size=float(pip_size_price); self.slippage_bps=float(slippage_bps_per_fill)
        self.multiplier=float(linear_multiplier); self.initial_equity=float(initial_equity)

    def apply_linear_cost_model(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(trades_df,pd.DataFrame) or trades_df.empty:
            raise LedgerError("Trade input must be a non-empty pandas DataFrame")
        missing=[c for c in REQUIRED if c not in trades_df.columns]
        if missing: raise LedgerError(f"Missing required raw trade columns: {missing}")
        overlap=sorted(DERIVED.intersection(trades_df.columns))
        if overlap: raise LedgerError(f"Input may already be costed; refusing double charge of derived columns: {overlap}")
        df=trades_df.copy()
        try:
            df["entry_time"]=pd.to_datetime(df["entry_time"],utc=True,errors="raise")
            df["exit_time"]=pd.to_datetime(df["exit_time"],utc=True,errors="raise")
            for c in ("entry_price","exit_price","direction","size","initial_risk"):
                df[c]=pd.to_numeric(df[c],errors="raise")
        except (ValueError,TypeError,OverflowError) as exc: raise LedgerError(f"Invalid timestamp/numeric field: {exc}") from exc
        arr=df[["entry_price","exit_price","direction","size","initial_risk"]].to_numpy(dtype=np.float64)
        if not np.isfinite(arr).all(): raise LedgerError("Trade input contains NaN/Inf")
        if (df[["entry_price","exit_price"]]<=0).any().any(): raise LedgerError("Prices must be positive")
        if not df["direction"].isin([-1,1]).all(): raise LedgerError("direction must be exactly +1 or -1")
        if (df[["size","initial_risk"]]<=0).any().any(): raise LedgerError("size and initial_risk must be positive")
        if (df["exit_time"]<df["entry_time"]).any(): raise LedgerError("exit_time cannot precede entry_time")
        df["_original_order"]=np.arange(len(df),dtype=np.int64)
        df=df.sort_values(["exit_time","_original_order"],kind="stable").reset_index(drop=True)
        df["gross_pnl"]=df["direction"]*(df["exit_price"]-df["entry_price"])*df["size"]*self.multiplier
        df["commission_cost"]=self.commission*df["size"]
        df["spread_cost"]=self.spread_pips*self.pip_size*df["size"]*self.multiplier
        # Assumed 5 bps per fill: charge each fill using its own entry/exit reference price.
        df["slippage_cost"]=(df["entry_price"]+df["exit_price"])*self.slippage_bps/10000.0*df["size"]*self.multiplier
        df["transaction_cost"]=df["commission_cost"]+df["spread_cost"]+df["slippage_cost"]
        df["net_pnl"]=df["gross_pnl"]-df["transaction_cost"]
        df["r_multiple"]=df["net_pnl"]/df["initial_risk"]
        df["equity_after_trade"]=self.initial_equity+df["net_pnl"].cumsum()
        df["equity_peak"]=np.maximum.accumulate(np.r_[self.initial_equity,df["equity_after_trade"].to_numpy()])[1:]
        df["drawdown_abs"]=df["equity_peak"]-df["equity_after_trade"]
        df["drawdown_fraction"]=np.where(df["equity_peak"]>0,df["drawdown_abs"]/df["equity_peak"],np.nan)
        df.drop(columns=["_original_order"],inplace=True)
        for col in DERIVED:
            if col in df and not np.isfinite(df[col].to_numpy(dtype=np.float64)).all(): raise LedgerError(f"Computed {col} has non-finite values")
        return df

    def generate_performance_ledger(self,trades_df:pd.DataFrame)->tuple[pd.DataFrame,dict[str,Any]]:
        ledger=self.apply_linear_cost_model(trades_df)
        net=ledger["net_pnl"].to_numpy(dtype=np.float64); r=ledger["r_multiple"].to_numpy(dtype=np.float64)
        wins=net[net>0]; losses=net[net<0]
        pf=float(wins.sum()/abs(losses.sum())) if len(losses) else ("infinite_no_losses" if len(wins) else None)
        summary={
            "schema":"atos.linear_trade_performance.v1","status":"COMPUTED_FROM_RAW_RECORDS_NOT_INSTRUMENT_QUALIFICATION",
            "total_trades":int(len(net)),"winning_trades":int((net>0).sum()),"losing_trades":int((net<0).sum()),
            "breakeven_trades":int((net==0).sum()),"win_rate":float((net>0).mean()),"expectancy_r":float(r.mean()),
            "median_r_multiple":float(np.median(r)),"profit_factor_net":pf,
            "max_drawdown_abs":float(ledger["drawdown_abs"].max()),"max_drawdown_fraction":float(ledger["drawdown_fraction"].max()),
            "total_gross_pnl":float(ledger["gross_pnl"].sum()),"total_net_pnl":float(net.sum()),
            "total_transaction_costs":float(ledger["transaction_cost"].sum()),
            "cost_breakdown":{"commission":float(ledger["commission_cost"].sum()),"spread":float(ledger["spread_cost"].sum()),"slippage":float(ledger["slippage_cost"].sum())},
            "initial_equity":self.initial_equity,"final_equity":float(ledger["equity_after_trade"].iloc[-1]),
            "cost_assumptions":{"commission_per_unit_round_trip":self.commission,"spread_pips_round_trip":self.spread_pips,
                "pip_size_price":self.pip_size,"spread_price_per_unit_round_trip":self.spread_pips*self.pip_size,
                "slippage_bps_per_fill":self.slippage_bps,"linear_multiplier":self.multiplier,
                "commission_source_verified":False,"spread_source_verified":False,"slippage_source_verified":False,
                "linear_contract_multiplier_verified":False,"qualification_status":"NOT_QUALIFIED_UNLESS_ECONOMICS_INDEPENDENTLY_VERIFIED"},
            "notes":["Input is raw pre-cost data; derived columns are rejected to prevent double-charging.",
                     "Profit factor uses post-cost net winning PnL divided by absolute post-cost net losing PnL.",
                     "Drawdown is measured on equity starting from initial_equity, in exit-time order.",
                     "This output is not proof that a corresponding Deriv linear instrument exists or that assumptions match realized costs."]}
        return ledger,summary

def run(args:argparse.Namespace)->int:
    source=args.trades.resolve(); ledger_path=args.ledger.resolve(); summary_path=args.summary.resolve()
    if not source.is_file(): raise LedgerError(f"Trade input does not exist: {source}")
    if ledger_path.exists() or summary_path.exists(): raise LedgerError("Refusing to overwrite evidence; choose new output paths")
    raw=pd.read_csv(source)
    engine=EmpiricalValidationEngine(commission_per_unit_round_trip=args.commission_per_unit,spread_pips_round_trip=args.spread_pips,
        pip_size_price=args.pip_size_price,slippage_bps_per_fill=args.slippage_bps_per_fill,linear_multiplier=args.linear_multiplier,initial_equity=args.initial_equity)
    ledger,summary=engine.generate_performance_ledger(raw)
    ledger_path.parent.mkdir(parents=True,exist_ok=True); summary_path.parent.mkdir(parents=True,exist_ok=True)
    ledger.to_csv(ledger_path,index=False)
    summary.update({"input_csv_sha256":sha256_file(source),"output_ledger_sha256":sha256_file(ledger_path),"input_path":str(source),"output_ledger_path":str(ledger_path)})
    summary_path.write_text(json.dumps(summary,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    summary_hash=sha256_file(summary_path)
    print(json.dumps(summary,indent=2,sort_keys=True,allow_nan=False)); print("INPUT_SHA256="+summary["input_csv_sha256"]); print("LEDGER_SHA256="+summary["output_ledger_sha256"]); print("SUMMARY_SHA256="+summary_hash)
    return 0

def main()->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("trades",type=Path); p.add_argument("--ledger",required=True,type=Path); p.add_argument("--summary",required=True,type=Path)
    p.add_argument("--commission-per-unit",required=True,type=float); p.add_argument("--spread-pips",required=True,type=float); p.add_argument("--pip-size-price",required=True,type=float)
    p.add_argument("--slippage-bps-per-fill",required=True,type=float); p.add_argument("--linear-multiplier",required=True,type=float); p.add_argument("--initial-equity",required=True,type=float)
    args=p.parse_args()
    try: return run(args)
    except (LedgerError,OSError,ValueError,KeyError,pd.errors.ParserError) as exc: print(f"PERFORMANCE LEDGER FAILED CLOSED: {type(exc).__name__}: {exc}",file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
