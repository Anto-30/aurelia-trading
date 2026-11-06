#!/usr/bin/env python3
"""Emit sanitized public-research and blocked account-plane evidence without reading secrets."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Mapping

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from runtime.security.deriv_auth_gate import ACCOUNT_CREDENTIAL_ENV_NAMES

DEFAULT_OUTPUT = Path("artifacts/deriv_auth_prerequisites.json")


def build_evidence(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environ is None else environ
    # Membership checks inspect only whether a credential key is present;
    # they never retrieve or compare secret values.
    credentials_present = any(name in env for name in ACCOUNT_CREDENTIAL_ENV_NAMES)
    mode_value = str(env.get("ACCOUNT_DERIV_AUTH_MODE", "oauth")).strip().lower()
    mode = mode_value if mode_value in {"oauth", "none"} else "invalid"

    return {
        "schema_version": "3",
        "public_research": {
            "status": "BLOCKED" if credentials_present else "CONFIGURED",
            "auth_mode": "none",
            "endpoint": "wss://api.derivws.com/trading/v1/options/ws/public",
            "account_credentials_mapped": False,
            "account_credentials_present_in_process": credentials_present,
        },
        "account_evidence": {
            "status": "BLOCKED",
            "auth_mode": mode,
            "account_credentials_present_in_process": credentials_present,
            "credentials_isolated_in_process": not credentials_present,
            "read_only_scope_supported": False,
            "reason": "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
        },
        "account_evidence_ready": False,
        "secret_values_exposed": False,
    }


def main() -> int:
    output = Path(os.getenv("DERIV_AUTH_PREREQUISITES_OUT", str(DEFAULT_OUTPUT)))
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence = build_evidence()
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)

    print("DERIV_PUBLIC_RESEARCH=" + str(evidence["public_research"]["status"]))
    print("DERIV_PUBLIC_AUTH_MODE=NONE")
    print("DERIV_ACCOUNT_EVIDENCE=" + str(evidence["account_evidence"]["status"]))
    print("DERIV_ACCOUNT_BLOCK_REASON=" + str(evidence["account_evidence"]["reason"]))
    print(
        "DERIV_ACCOUNT_CREDENTIALS_PRESENT_IN_PROCESS="
        + str(evidence["account_evidence"]["account_credentials_present_in_process"]).lower()
    )
    print(
        "DERIV_CREDENTIALS_ISOLATED_IN_PROCESS="
        + str(evidence["account_evidence"]["credentials_isolated_in_process"]).lower()
    )
    print("DERIV_READ_ONLY_SCOPE_SUPPORTED=false")
    print("SECRET_VALUES_EXPOSED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
