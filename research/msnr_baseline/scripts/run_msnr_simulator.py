#!/usr/bin/env python3
"""Load the hash-pinned simulator source fragments stored beside this file."""
from pathlib import Path as _Path
_here = _Path(__file__).resolve()
_parts_dir = _here.parent / "_simulator_parts"
_parts = sorted(_parts_dir.glob("part[0-9][0-9][0-9].txt"))
if len(_parts) != 6:
    raise RuntimeError(f"Expected 6 simulator source fragments, got {len(_parts)}")
_source = "".join(part.read_text(encoding="utf-8") for part in _parts)
exec(compile(_source, str(_here), "exec"), globals())
