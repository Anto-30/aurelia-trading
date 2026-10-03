from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from typing import Iterable
@dataclass(frozen=True)
class OOSCell: strategy:str; symbol:str; regime:str; trades:int
@dataclass(frozen=True)
class OOSValidationResult: sealed_prospective_data:bool; retuning_after_seal:bool; min_trades_per_cell:int; qualified:bool; failures:tuple[str,...]
def validate_prospective_oos(cells:Iterable[OOSCell],*,sealed_prospective_data:bool,retuning_after_seal:bool,min_trades_required=100):
 cells=list(cells); failures=[]
 if not sealed_prospective_data: failures.append("PROSPECTIVE_DATA_NOT_SEALED")
 if retuning_after_seal: failures.append("RETUNING_AFTER_PROSPECTIVE_SEAL")
 minimum=min((c.trades for c in cells),default=0)
 if not cells: failures.append("NO_STRATEGY_SYMBOL_REGIME_CELLS")
 for c in cells:
  if c.trades<min_trades_required: failures.append(f"UNDERPOWERED:{c.strategy}:{c.symbol}:{c.regime}:{c.trades}")
 return OOSValidationResult(sealed_prospective_data,retuning_after_seal,minimum,not failures,tuple(failures))
def group_by_cell(rows:Iterable[dict]):
 counts=defaultdict(int)
 for r in rows: counts[(r["strategy"],r["symbol"],r["regime"])] += 1
 return [OOSCell(*k,trades=v) for k,v in sorted(counts.items())]
