from __future__ import annotations

"""Classify recovered R100 state before continuing a frozen campaign."""

import json
from pathlib import Path

from research.r100_prospective_oos_collector import STRATEGY_ID, STRATEGY_VERSION, research_config_hash

def inspect_state(path: Path) -> str:
    if not path.exists():
        return 'R100_NO_STATE'
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 'R100_ROLLOVER_REQUIRED:R100_STATE_UNREADABLE'
    if state.get('schema') != 'aurelia.r100.prospective_oos.v1':
        return 'R100_ROLLOVER_REQUIRED:R100_STATE_SCHEMA_MISMATCH'
    manifest = state.get('manifest')
    if not isinstance(manifest, dict):
        return 'R100_ROLLOVER_REQUIRED:R100_STATE_MANIFEST_MISSING'
    if manifest.get('sealed'):
        return 'R100_ROLLOVER_REQUIRED:R100_ARCHIVE_ALREADY_SEALED'
    if manifest.get('strategy_id') != STRATEGY_ID:
        return 'R100_ROLLOVER_REQUIRED:R100_STRATEGY_MISMATCH'
    if manifest.get('strategy_version') != STRATEGY_VERSION:
        return 'R100_ROLLOVER_REQUIRED:R100_STRATEGY_VERSION_MISMATCH'
    bound_config = str(manifest.get('config_hash') or '').strip()
    if bound_config and bound_config != research_config_hash():
        return 'R100_ROLLOVER_REQUIRED:R100_CONFIG_HASH_MISMATCH'
    return 'R100_COMPATIBLE'

def main() -> int:
    print(inspect_state())
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
