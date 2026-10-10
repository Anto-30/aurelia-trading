from __future__ import annotations

import os


SECRET_NAMES = (
    "DERIV_AUTH_TOKEN",
    "DERIV_PAT",
    "DERIV_APP_ID",
    "DERIV_EXPECTED_LOGINID",
    "DERIV_AUTHORIZED_ACCOUNT_ID",
    "DERIV_EXPECTED_CURRENCY",
    "DERIV_AUTH_MODE",
)

DEPLOYMENT_SECRET_NAMES = (
    "AURELIA_HOST",
    "AURELIA_USER",
    "AURELIA_SSH_KEY",
    "AURELIA_KNOWN_HOSTS",
    "AURELIA_ATTESTATION_SIGNING_KEY",
)


def present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def main() -> int:
    for name in SECRET_NAMES:
        print(f"{name}_PRESENT={'true' if present(name) else 'false'}")

    auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower() or "pat"
    auth_mode_valid = auth_mode in {"pat", "oauth"}
    auth_present = present("DERIV_AUTH_TOKEN") or present("DERIV_PAT")
    login_present = present("DERIV_EXPECTED_LOGINID") or present("DERIV_AUTHORIZED_ACCOUNT_ID")
    currency_present = present("DERIV_EXPECTED_CURRENCY")
    deriv_core = auth_present and login_present and currency_present
    deriv_configured = (
        deriv_core
        and auth_mode_valid
        and (auth_mode != "pat" or present("DERIV_APP_ID"))
    )

    print(f"DERIV_AUTH_MODE_PRESENT={'true' if present('DERIV_AUTH_MODE') else 'false'}")
    print(f"DERIV_AUTH_MODE_VALID={'true' if auth_mode_valid else 'false'}")
    print(f"DERIV_AUTH_MODE_EFFECTIVE={auth_mode.upper() if auth_mode_valid else 'INVALID'}")
    print(f"DERIV_AUTH_CONFIGURED={'true' if deriv_configured else 'false'}")

    for name in DEPLOYMENT_SECRET_NAMES:
        print(f"{name}_PRESENT={'true' if present(name) else 'false'}")
    deployment_secrets_present = all(present(name) for name in DEPLOYMENT_SECRET_NAMES)
    print(
        "AURELIA_DEPLOYMENT_SECRET_STORE_CONFIGURED="
        + ("true" if deployment_secrets_present else "false")
    )
    print(
        "AURELIA_PRODUCTION_PREREQUISITES_CONFIGURED="
        + ("true" if deriv_configured and deployment_secrets_present else "false")
    )
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    print("LIVE_EXECUTION=BLOCKED")
    print("CAPITAL_MOVEMENT_PERMITTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
