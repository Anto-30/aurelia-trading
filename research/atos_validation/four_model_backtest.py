"""Matched four-model evaluation harness. Input is a caller-supplied, audited trade table.

Required columns: timestamp, strategy, r_gross, cost_r, fold, regime.
r_gross and cost_r are expressed in R; net R = r_gross - cost_r.
The harness deliberately does not invent MSNR entries or Deriv costs.
"""
from __future__ import annotations
import argparse
import numpy as np
import pandas as pd

MODEL_ORDER=("alpha_beta_hmm","gaussian_hmm","ma_control","unfiltered_msnr")

def summarize(r: pd.Series, folds: pd.Series) -> dict:
    a=r.to_numpy(dtype=float)
    if len(a)==0: return dict(expectancy_r=np.nan,profit_factor=np.nan,max_drawdown_r=np.nan,sample_size=0,fold_stability=np.nan)
    if not np.isfinite(a).all(): raise ValueError("non-finite net R values")
    wins=a[a>0].sum(); losses=-a[a<0].sum()
    pf=float(wins/losses) if losses>0 else (float("inf") if wins>0 else 0.0)
    eq=np.cumsum(a); dd=float(np.min(eq-np.maximum.accumulate(np.r_[0.0,eq])))
    fold_means=pd.DataFrame({"r":a,"fold":folds.to_numpy()}).groupby("fold").r.mean()
    return dict(expectancy_r=float(a.mean()),profit_factor=pf,max_drawdown_r=dd,
                sample_size=len(a),fold_stability=float(fold_means.var(ddof=1)) if len(fold_means)>1 else np.nan)

def evaluate(path: str) -> pd.DataFrame:
    df=pd.read_csv(path,parse_dates=["timestamp"])
    required={"timestamp","strategy","r_gross","cost_r","fold"}
    if not required.issubset(df.columns): raise ValueError(f"missing columns: {sorted(required-set(df.columns))}")
    df=df.sort_values("timestamp")
    if df.timestamp.isna().any() or df.timestamp.duplicated().any(): raise ValueError("timestamps must be non-null and unique per input trade row")
    if not np.isfinite(df[["r_gross","cost_r"]].to_numpy(dtype=float)).all(): raise ValueError("invalid R/costs")
    df["net_r"]=df.r_gross-df.cost_r
    absent=set(MODEL_ORDER)-set(df.strategy.unique())
    if absent: raise ValueError(f"all four matched strategies required; missing {sorted(absent)}")
    # Matched period is required; trade events may differ but fold boundaries must be shared.
    fold_sets={s:set(df.loc[df.strategy==s,"fold"].unique()) for s in MODEL_ORDER}
    common=set.intersection(*fold_sets.values())
    if not common: raise ValueError("no common walk-forward folds across all models")
    rows=[]
    for name in MODEL_ORDER:
        sub=df[(df.strategy==name)&df.fold.isin(common)]
        rows.append({"model":name,**summarize(sub.net_r,sub.fold)})
    return pd.DataFrame(rows).set_index("model").loc[list(MODEL_ORDER)].reset_index()

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("trades_csv",help="audited trade-level output with realized costs and common WFA fold IDs")
    p.add_argument("--out",default="four_model_metrics.csv")
    args=p.parse_args()
    result=evaluate(args.trades_csv)
    result.to_csv(args.out,index=False)
    print(result.to_string(index=False))
