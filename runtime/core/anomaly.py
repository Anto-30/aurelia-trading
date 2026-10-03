from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ExecutionAnomaly:
    code:str
    severity:str
    metric:str
    baseline:float
    observed:float
    ratio:float

class ExecutionAnomalyDetector:
    def __init__(self,ratio_threshold:float=3.0): self.ratio_threshold=ratio_threshold
    def compare(self,metric:str,baseline:float,observed:float)->ExecutionAnomaly|None:
        if baseline<=0:return ExecutionAnomaly("BASELINE_NON_POSITIVE","WARN",metric,baseline,observed,float("inf"))
        ratio=observed/baseline
        if ratio>=self.ratio_threshold:return ExecutionAnomaly("EXECUTION_RATE_ANOMALY","WARN",metric,baseline,observed,ratio)
        return None
