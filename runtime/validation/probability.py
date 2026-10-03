from dataclasses import dataclass
from math import log
@dataclass(frozen=True)
class CalibrationMetrics: brier_score:float; log_loss:float; sample_count:int; valid:bool; drift_detected:bool
def calibration_metrics(probabilities,outcomes):
 if len(probabilities)!=len(outcomes) or not probabilities:return CalibrationMetrics(0,0,0,False,False)
 if any(not 0<=p<=1 for p in probabilities):return CalibrationMetrics(0,0,len(probabilities),False,False)
 brier=sum((p-y)**2 for p,y in zip(probabilities,outcomes))/len(probabilities); ll=-sum(y*log(max(p,1e-12))+(1-y)*log(max(1-p,1e-12)) for p,y in zip(probabilities,outcomes))/len(probabilities)
 return CalibrationMetrics(brier,ll,len(probabilities),True,False)
def detect_drift(reference_mean,current_mean,tolerance=.05):return abs(reference_mean-current_mean)>tolerance
