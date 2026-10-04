from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "skills"
TARGETS = [ROOT / ".claude" / "skills", ROOT / ".grok" / "skills", ROOT / ".agents" / "skills"]
PREFIXES = ("aurelia-", "research-", "security-", "browser-", "ci-", "evidence-")

def main() -> None:
    selected = [p for p in SOURCE.iterdir() if p.is_dir() and p.name.startswith(PREFIXES)]
    if not selected:
        raise SystemExit("No canonical agent skills found")
    for target in TARGETS:
        target.mkdir(parents=True, exist_ok=True)
        for skill in selected:
            destination = target / skill.name
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(skill, destination)
    print(f"SYNCED_SKILLS={len(selected)}")
    for target in TARGETS:
        print(f"TARGET={target.relative_to(ROOT)}")

if __name__ == "__main__":
    main()