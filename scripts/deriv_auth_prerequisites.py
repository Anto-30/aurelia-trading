#!/usr/bin/env python3
"""Emit sanitized Deriv authentication prerequisite evidence for CI.

Only booleans and allowlisted enum values are persisted. Raw credentials,
account identifiers, auth-mode values, and currency values are never written.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

SUPPORTED_AUTH_MODES = frozenset({"pat", "oauth"})
SUPPORTED_CURRENCIES = frozenset({"USD"})
DEFAULT_OUTPUT = Path("artifacts/deriv_auth_prerequisites.json")


def build_evidence(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environ is None else environ

    token_present = bool(env.get("DERIV_AUTH_TOKEN", "").strip())
    loginid_present = bool(
        env.get("DERIV_EXPECTED_LOGINID", "").strip()
        or env.get("DERIV_AUTHORIZED_ACCOUNT_ID", "").strip()
    )
    raw_mode = env.get("DERIV_AUTH_MODE", "pat").strip().lower() or "pat"
    mode_valid = raw_mode in SUPPORTED_AUTH_MODES
    safe_mode = raw_mode if mode_valid else "invalid"
    app_id_present = bool(env.get("DERIV_APP_ID", "").strip())

    raw_currency = env.get("DERIV_EXPECTED_CURRENCY", "").strip().upper()
    currency_valid = raw_currency in SUPPORTED_CURRENCIES
    safe_currency = raw_currency if currency_valid else ("missing" if not raw_currency else "invalid")

    requirements = {
        "token_present": token_present,
        "expected_loginid_present": loginid_present,
        "auth_mode_valid": mode_valid,
        "app_id_present_when_pat": app_id_present if safe_mode == "pat" else safe_mode == "oauth",
        "expected_currency_present": currency_valid,
    }
    return {
        "schema_version": "1",
        "auth_mode": safe_mode,
        "expected_currency": safe_currency,
        "configured": all(requirements.values()),
        "requirements": requirements,
        "secret_values_exposed": False,
    }


def main() -> int:
    output = Path(os.getenv("DERIV_AUTH_PREREQUISITES_OUT", str(DEFAULT_OUTPUT)))
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence = build_evidence()
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(output)

    print("DERIV_AUTH_PREREQUISITES=" + ("READY" if evidence["configured"] else "NOT_READY"))
    mode = evidence["auth_mode"]
    print("DERIV_AUTH_MODE=" + (str(mode).upper() if mode in SUPPORTED_AUTH_MODES else "INVALID"))
    print("DERIV_TOKEN_PRESENT=" + str(evidence["requirements"]["token_present"]).lower())
    print("DERIV_EXPECTED_LOGINID_PRESENT=" + str(evidence["requirements"]["expected_loginid_present"]).lower())
    print("DERIV_APP_ID_REQUIRED=" + str(mode == "pat").lower())
    print("DERIV_APP_ID_PRESENT_WHEN_REQUIRED=" + str(evidence["requirements"]["app_id_present_when_pat"]).lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
