#!/usr/bin/env python3
"""Emit sanitized state for public Deriv research and blocked account evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

DEFAULT_OUTPUT = Path("artifacts/deriv_auth_prerequisites.json")


def build_evidence(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environ is None else environ
    oauth_token = str(env.get("DERIV_OAUTH_ACCESS_TOKEN", "")).strip()
    pat_token = str(env.get("DERIV_PAT", "")).strip()
    generic_token = str(env.get("DERIV_AUTH_TOKEN", "")).strip()
    refresh_token = (
        str(env.get("DERIV_OAUTH_REFRESH_TOKEN", "")).strip()
        or str(env.get("DERIV_REFRESH_TOKEN", "")).strip()
    )
    mode = str(env.get("ACCOUNT_DERIV_AUTH_MODE", "oauth")).strip().lower()
    tokens_equal = bool(oauth_token and pat_token and oauth_token == pat_token)
    credentials_isolated = bool(oauth_token) and not (
        pat_token or generic_token or refresh_token or tokens_equal
    )

    account_reason = (
        "ACCOUNT_PLANE_REQUIRES_EXPLICIT_OAUTH_MODE"
        if mode != "oauth"
        else "OAUTH_TOKEN_EQUALS_PAT"
        if tokens_equal
        else "ACCOUNT_PLANE_PAT_PRESENT"
        if pat_token
        else "GENERIC_TOKEN_FALLBACK_BLOCKED"
        if generic_token
        else "DERIV_OAUTH_REFRESH_TOKEN_UNSUPPORTED"
        if refresh_token
        else "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"
    )

    return {
        "schema_version": "2",
        "public_research": {
            "status": "READY",
            "auth_mode": "none",
            "endpoint": "wss://api.derivws.com/trading/v1/options/ws/public",
            "account_credentials_mapped": False,
        },
        "account_evidence": {
            "status": "BLOCKED",
            "auth_mode": mode if mode in {"oauth", "none"} else "invalid",
            "oauth_access_token_present": bool(oauth_token),
            "pat_present": bool(pat_token),
            "generic_token_present": bool(generic_token),
            "refresh_token_present": bool(refresh_token),
            "oauth_pat_values_equal": tokens_equal,
            "credentials_isolated_in_process": credentials_isolated,
            "read_only_scope_supported": False,
            "reason": account_reason,
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
        json.dumps(evidence, indent=2, sort_keys=True) + "\\n",
        encoding="utf-8",
    )
    temporary.replace(output)

    print("DERIV_PUBLIC_RESEARCH=" + str(evidence["public_research"]["status"]))
    print("DERIV_PUBLIC_AUTH_MODE=NONE")
    print("DERIV_ACCOUNT_EVIDENCE=" + str(evidence["account_evidence"]["status"]))
    print("DERIV_ACCOUNT_BLOCK_REASON=" + str(evidence["account_evidence"]["reason"]))
    print(
        "DERIV_OAUTH_TOKEN_PRESENT="
        + str(evidence["account_evidence"]["oauth_access_token_present"]).lower()
    )
    print("DERIV_PAT_PRESENT=" + str(evidence["account_evidence"]["pat_present"]).lower())
    print(
        "DERIV_OAUTH_PAT_VALUES_EQUAL="
        + str(evidence["account_evidence"]["oauth_pat_values_equal"]).lower()
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
