from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal,InvalidOperation,ROUND_DOWN

@dataclass(frozen=True)
class Money:
    amount:Decimal
    currency:str
    def normalized(self,places:int=2)->"Money":
        quantum=Decimal(1).scaleb(-places)
        return Money(self.amount.quantize(quantum,rounding=ROUND_DOWN),self.currency)

def parse_money(value, currency:str)->Money:
    try: amount=Decimal(str(value))
    except (InvalidOperation,ValueError) as exc: raise ValueError("INVALID_MONEY") from exc
    if not amount.is_finite() or amount<0: raise ValueError("INVALID_MONEY")
    if not currency or not currency.isascii(): raise ValueError("INVALID_CURRENCY")
    return Money(amount,currency)
