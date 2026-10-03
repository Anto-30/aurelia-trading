from abc import ABC,abstractmethod
from typing import Any,AsyncIterator
from runtime.core.models import AccountIdentity,BrokerResult,CapitalSnapshot,MarketTick
class BrokerAdapter(ABC):
 @abstractmethod
 async def connect(self)->AccountIdentity: raise NotImplementedError
 @abstractmethod
 async def get_balance(self)->CapitalSnapshot: raise NotImplementedError
 @abstractmethod
 async def active_symbols(self)->list[dict[str,Any]]: raise NotImplementedError
 @abstractmethod
 async def subscribe_ticks(self,symbol:str)->AsyncIterator[MarketTick]: raise NotImplementedError
 @abstractmethod
 async def submit_authorized_order(self,payload:dict[str,Any])->BrokerResult: raise NotImplementedError
 @abstractmethod
 async def get_contract_status(self,contract_id:str)->dict[str,Any]: raise NotImplementedError
 @abstractmethod
 async def close(self)->None: raise NotImplementedError
