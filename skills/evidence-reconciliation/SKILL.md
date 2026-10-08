---
name: evidence-reconciliation
description: Validate operational claims against independent current evidence and reconcile contradictory states.
---
# evidence-reconciliation
Separate claimed state from observed state. For broker state, prefer authenticated broker responses and transaction records over local flags. Check timestamp, account identity, source, freshness, request/response correlation, and idempotency. If evidence conflicts, mark the state UNKNOWN and stop promotion or execution.
