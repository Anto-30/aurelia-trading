from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class StrategyStage(str,Enum):
    EXPERIMENTAL="EXPERIMENTAL"; REPLAYABLE="REPLAYABLE"; VALIDATED="VALIDATED"; CALIBRATED="CALIBRATED"; SHADOW="SHADOW"; CANARY="CANARY"; PRODUCTION="PRODUCTION"; SUSPENDED="SUSPENDED"

_PROMOTION={
    StrategyStage.EXPERIMENTAL:StrategyStage.REPLAYABLE,
    StrategyStage.REPLAYABLE:StrategyStage.VALIDATED,
    StrategyStage.VALIDATED:StrategyStage.CALIBRATED,
    StrategyStage.CALIBRATED:StrategyStage.SHADOW,
    StrategyStage.SHADOW:StrategyStage.CANARY,
    StrategyStage.CANARY:StrategyStage.PRODUCTION,
}

@dataclass(frozen=True)
class StrategyPromotion:
    strategy_id:str
    version:str
    stage:StrategyStage
    evidence_ids:tuple[str,...]
    approved_by:str

@dataclass
class StrategyGovernance:
    stages:dict[str,StrategyStage]
    def promote(self,strategy_id:str,evidence_ids:tuple[str,...],approved_by:str)->StrategyStage:
        current=self.stages.get(strategy_id,StrategyStage.EXPERIMENTAL)
        target=_PROMOTION.get(current)
        if target is None: raise ValueError(f"NO_PROMOTION_AVAILABLE:{current.value}")
        if not evidence_ids or not approved_by: raise ValueError("PROMOTION_REQUIRES_EVIDENCE_AND_REVIEW")
        self.stages[strategy_id]=target
        return target
    def demote(self,strategy_id:str,target:StrategyStage)->StrategyStage:
        current=self.stages.get(strategy_id,StrategyStage.EXPERIMENTAL)
        if target not in {StrategyStage.SHADOW,StrategyStage.SUSPENDED,StrategyStage.CANARY}:
            raise ValueError("INVALID_DEMOTION_TARGET")
        if current==StrategyStage.EXPERIMENTAL: return current
        self.stages[strategy_id]=target
        return target
