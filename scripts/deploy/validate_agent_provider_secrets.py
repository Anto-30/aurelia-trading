from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path


# Provider-only credentials. Broker tokens, GitHub tokens, deployment secrets,
# and arbitrary shell/runtime configuration are intentionally not accepted.
ALLOWED_SECRET_NAMES = frozenset({
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "XAI_API_KEY",
    "ZAI_API_KEY",
    "ZHIPU_API_KEY",
    "MOONSHOT_API_KEY",
    "KIMI_API_KEY",
    "LITELLM_API_KEY",
    "HERMES_API_KEY",
})


def validate_provider_secret_file(path: str | Path) -> dict[str, object]:
    file_path = Path(path)
    try:
        info = file_path.lstat()
    except FileNotFoundError:
        return {
            "status": "ABSENT",
            "path": str(file_path),
            "credential_names": [],
            "credential_count": 0,
            "secret_values_emitted": False,
            "broker_credentials_allowed": False,
        }
    except OSError as exc:
        raise ValueError("AGENT_PROVIDER_SECRET_FILE_UNREADABLE") from exc

    if stat.S_ISLNK(info.st_mode):
        raise ValueError("AGENT_PROVIDER_SECRET_FILE_MUST_NOT_BE_SYMLINK")
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("AGENT_PROVIDER_SECRET_FILE_MUST_BE_REGULAR_FILE")
    if stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError("AGENT_PROVIDER_SECRET_FILE_PERMISSIONS_MUST_BE_0600")

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError("AGENT_PROVIDER_SECRET_FILE_UNREADABLE") from exc

    seen: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        if not line or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"AGENT_PROVIDER_SECRET_LINE_INVALID:{line_number}")
        name, value = line.split("=", 1)
        if not name or name.strip() != name or not name.replace("_", "").isalnum():
            raise ValueError(f"AGENT_PROVIDER_SECRET_NAME_INVALID:{line_number}")
        if name not in ALLOWED_SECRET_NAMES:
            # Only variable names are included; never echo the line or its value.
            raise ValueError(f"AGENT_PROVIDER_SECRET_NAME_NOT_ALLOWED:{name}")
        if name in seen:
            raise ValueError(f"AGENT_PROVIDER_SECRET_NAME_DUPLICATE:{name}")
        if not value or value.strip() != value or "\r" in value or "\n" in value:
            raise ValueError(f"AGENT_PROVIDER_SECRET_VALUE_INVALID:{name}")
        seen.add(name)

    return {
        "status": "VALID",
        "path": str(file_path),
        "credential_names": sorted(seen),
        "credential_count": len(seen),
        "secret_values_emitted": False,
        "broker_credentials_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    args = parser.parse_args()
    try:
        result = validate_provider_secret_file(args.path)
    except ValueError as exc:
        print(f"AGENT_PROVIDER_SECRET_STORE=BLOCKED:{exc}")
        return 2
    print(f"AGENT_PROVIDER_SECRET_STORE={result['status']}")
    print(f"AGENT_PROVIDER_SECRET_COUNT={result['credential_count']}")
    print("AGENT_PROVIDER_SECRET_VALUES_EMITTED=FALSE")
    print("AGENT_PROVIDER_BROKER_CREDENTIALS_ALLOWED=FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
