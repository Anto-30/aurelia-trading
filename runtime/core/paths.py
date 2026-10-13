from __future__ import annotations

import os
from pathlib import Path


DEFAULT_STATE_DIR = Path(os.getenv("AURELIA_STATE_DIR", "/var/lib/aurelia"))


def state_path(environment_name: str, filename: str) -> Path:
    """Resolve durable runtime state paths while preserving explicit overrides.

    Production state defaults to AURELIA_STATE_DIR (default /var/lib/aurelia),
    not the OS temporary directory. Deployments should mount this directory on
    durable storage and restrict write access to the AURELIA runtime identity.
    """
    configured = os.getenv(environment_name, "").strip()
    if configured:
        return Path(configured)
    state_dir = Path(os.getenv("AURELIA_STATE_DIR", str(DEFAULT_STATE_DIR)))
    return state_dir / filename
