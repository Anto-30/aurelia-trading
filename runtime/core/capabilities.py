from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class Capability(str, Enum):
    READ_MARKET_DATA="READ_MARKET_DATA"
    READ_ACCOUNT="READ_ACCOUNT"
    GENERATE_SIGNAL="GENERATE_SIGNAL"
    RUN_BACKTEST="RUN_BACKTEST"
    CREATE_ORDER_INTENT="CREATE_ORDER_INTENT"
    AUTHORIZE_ORDER="AUTHORIZE_ORDER"
    SUBMIT_ORDER="SUBMIT_ORDER"
    MODIFY_RISK="MODIFY_RISK"
    MODIFY_PRODUCTION_CONFIG="MODIFY_PRODUCTION_CONFIG"

@dataclass(frozen=True)
class CapabilitySet:
    capabilities:frozenset[Capability]
    def allows(self, capability:Capability)->bool:
        return capability in self.capabilities

RESEARCH_CAPABILITIES=CapabilitySet(frozenset({
    Capability.READ_MARKET_DATA,Capability.GENERATE_SIGNAL,Capability.RUN_BACKTEST
}))
EXECUTION_CAPABILITIES=CapabilitySet(frozenset({
    Capability.CREATE_ORDER_INTENT,Capability.AUTHORIZE_ORDER,Capability.SUBMIT_ORDER
}))
