from enum import Enum

class RetryClass(str,Enum):
    SAFE="SAFE_TO_RETRY"
    RECONCILE_FIRST="RECONCILE_BEFORE_RETRY"
    NEVER="NEVER_RETRY"

READ_RETRY=RetryClass.SAFE
WRITE_UNKNOWN_RETRY=RetryClass.RECONCILE_FIRST
CAPITAL_AUTH_RETRY=RetryClass.NEVER

def retry_class(operation:str)->RetryClass:
    if operation in {"active_symbols","ticks","trading_times","balance_read","portfolio_read","statement_read"}: return READ_RETRY
    if operation in {"buy","sell","cancel","contract_update"}: return WRITE_UNKNOWN_RETRY
    return CAPITAL_AUTH_RETRY
