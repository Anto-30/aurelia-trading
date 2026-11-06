from __future__ import annotations

import traceback
from pathlib import Path


def safe_exception_frames(
    exc: BaseException,
    *,
    root: Path,
    limit: int = 8,
) -> tuple[str, ...]:
    """Return traceback locations without exception messages or source lines.

    Exception messages and source lines can contain credentials, OTPs, account
    identifiers, or broker payloads. Emit only repository-relative file,
    line, and function metadata for bounded diagnostic value.
    """
    if limit <= 0:
        return ()
    root_path = root.resolve()
    frames = traceback.extract_tb(exc.__traceback__)[-limit:]
    result: list[str] = []
    for frame in frames:
        path = Path(frame.filename)
        try:
            display_path = path.resolve().relative_to(root_path).as_posix()
        except (OSError, ValueError):
            display_path = path.name
        function = "".join(
            character if character.isalnum() or character in "._-" else "_"
            for character in frame.name
        )
        result.append(f"{display_path}:{frame.lineno}:{function}")
    return tuple(result)
