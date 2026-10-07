"""AURELIA ML evidence and leakage contracts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Sequence

TIMING_FEATURES=("high_time_position","low_time_position","high_before_low","extreme_time_gap","time_to_high","time_to_low")

@dataclass(frozen=True)
class MLEvidence:
    model_id:str; signal:str; p_win:float; expected_return:float; expected_mae:float; expected_mfe:float
    regime:str; calibration_status:str; oos_status:str; feature_freshness:str
    def validate(self)->None:
        if not self.model_id.strip(): raise ValueError("model_id required")
        if self.signal not in {"LONG","SHORT","NONE"}: raise ValueError("invalid signal")
        if not 0<=self.p_win<=1: raise ValueError("p_win must be in [0,1]")
        if self.calibration_status not in {"PASS","FAIL","UNKNOWN"}: raise ValueError("invalid calibration status")
        if self.oos_status not in {"PASS","FAIL","UNKNOWN"}: raise ValueError("invalid OOS status")
        if self.feature_freshness not in {"FRESH","STALE","UNKNOWN"}: raise ValueError("invalid freshness")

def reject_future_features(feature_available_at:Mapping[str,float],decision_ts:float)->None:
    for name,available_at in feature_available_at.items():
        if available_at>decision_ts: raise ValueError(f"look-ahead feature detected: {name}")

def validate_feature_vector(names:Sequence[str],values:Sequence[float])->None:
    if len(names)!=len(values): raise ValueError("feature names/values length mismatch")
    if len(set(names))!=len(names): raise ValueError("duplicate feature names")
