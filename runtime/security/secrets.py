from __future__ import annotations

import re
from dataclasses import dataclass

_SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-+/=]{16,}"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*[^\s]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
)

@dataclass(frozen=True)
class SecretFinding:
    pattern: str
    start: int

def scan_text(text: str) -> list[SecretFinding]:
    findings=[]
    for pattern in _SECRET_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(SecretFinding(pattern.pattern, match.start()))
    return findings

def is_clean(text: str) -> bool:
    return not scan_text(text)
