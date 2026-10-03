from __future__ import annotations

import os
from pathlib import Path

from runtime.broker.executor import CapitalPlaneExecutor
from runtime.core.fencing import ExecutionFence
from runtime.core.journal import AppendOnlyJournal
from runtime.core.persistent import PersistentExecutionFence, PersistentIdempotencyStore, PersistentLedger
from runtime.core.reconcile import Reconciler
from runtime.core.runtime_config import load_config_hash
from runtime.core.state import RuntimeStateMachine


def build_capital_plane(*, broker, root: Path | None = None) -> CapitalPlaneExecutor:
    '''Construct the only capital-moving executor with restart-safe state.'''
    root = root or Path.cwd()
    state_dir = Path(os.getenv("AURELIA_STATE_DIR", str(root / "state")))
    state_dir.mkdir(parents=True, exist_ok=True)

    journal = AppendOnlyJournal(state_dir / "events.ndjson")
    idempotency = PersistentIdempotencyStore(state_dir / "idempotency.json")
    fence = PersistentExecutionFence(state_dir / "execution-fence.txt")
    ledger = PersistentLedger(state_dir / "ledger.json")
    state_machine = RuntimeStateMachine()
    config_hash = load_config_hash(root)

    return CapitalPlaneExecutor(
        broker,
        journal=journal,
        ledger=ledger,
        idempotency=idempotency,
        fence=fence,
        state=state_machine,
        reconciler=Reconciler(),
        source_hash="runtime-baseline",
        config_hash=config_hash,
        live_lock_path=root / "config" / "LIVE_LOCK.yaml",
    )
