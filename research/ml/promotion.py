"""Deterministic model-promotion contract."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class PromotionEvidence:
    oos_pass:bool; calibration_pass:bool; economics_pass:bool; robustness_pass:bool; provenance_pass:bool; shadow_pass:bool
    @property
    def qualified(self)->bool: return all((self.oos_pass,self.calibration_pass,self.economics_pass,self.robustness_pass,self.provenance_pass,self.shadow_pass))
def promotion_decision(evidence:PromotionEvidence)->str:
    return "PROMOTION_CANDIDATE" if evidence.qualified else "RESEARCH"
