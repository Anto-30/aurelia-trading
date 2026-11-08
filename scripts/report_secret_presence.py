from __future__ import annotations

import os


REPORTED_BINDING_NAMES = (
    "DERIV_AUTH_TOKEN",
    "DERIV_PAT",
    "DERIV_APP_ID",
    "DERIV_EXPECTED_LOGINID",
    "DERIV_AUTHORIZED_ACCOUNT_ID",
    "DERIV_EXPECTED_CURRENCY",
    "DERIV_AUTH_MODE",
    "DERIV_ENVIRONMENT",
)

DEPLOYMENT_SECRET_NAMES = (
    "AURELIA_HOST",
    "AURELIA_USER",
    "AURELIA_SSH_KEY",
    "AURELIA_KNOWN_HOSTS",
    "AURELIA_ATTESTATION_SIGNING_KEY",
    "AURELIA_OPERATOR_RESET_SIGNING_KEY",
)


def present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def main() -> int:
    # Presence only: never print, hash, or transmit any secret/configuration value.
    for name in REPORTED_BINDING_NAMES:
        print(f"{name}_PRESENT={'true' if present(name) else 'false'}")

    auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower() or "pat"
    auth_mode_valid = auth_mode in {"pat", "oauth"}
    auth_present = present("DERIV_AUTH_TOKEN") or present("DERIV_PAT")
    login_present = present("DERIV_EXPECTED_LOGINID") or present("DERIV_AUTHORIZED_ACCOUNT_ID")
    currency_supported = os.getenv("DERIV_EXPECTED_CURRENCY", "").strip().upper() == "USD"
    environment = os.getenv("DERIV_ENVIRONMENT", "real").strip().lower() or "real"
    environment_valid = environment in {"real", "demo"}

    deriv_configured = (
        auth_present
        and login_present
        and currency_supported
        and environment_valid
        and auth_mode_valid
        and (auth_mode != "pat" or present("DERIV_APP_ID"))
    )

    print(f"DERIV_AUTH_MODE_VALID={'true' if auth_mode_valid else 'false'}")
    print(f"DERIV_AUTH_MODE_EFFECTIVE={auth_mode.upper() if auth_mode_valid else 'INVALID'}")
    print(f"DERIV_EXPECTED_CURRENCY_SUPPORTED={str(currency_supported).lower()}")
    print(f"DERIV_ENVIRONMENT_VALID={str(environment_valid).lower()}")
    print(f"DERIV_ENVIRONMENT_EFFECTIVE={environment.upper() if environment_valid else 'INVALID'}")
    print(f"DERIV_AUTH_CONFIGURED={'true' if deriv_configured else 'false'}")

    for name in DEPLOYMENT_SECRET_NAMES:
        print(f"{name}_PRESENT={'true' if present(name) else 'false'}")
    operator_reset_key_length_valid = (
        len(os.getenv("AURELIA_OPERATOR_RESET_SIGNING_KEY", "").strip()) >= 32
    )
    print(
        "AURELIA_OPERATOR_RESET_SIGNING_KEY_LENGTH_VALID="
        + ("true" if operator_reset_key_length_valid else "false")
    )
    deployment_secrets_present = (
        all(present(name) for name in DEPLOYMENT_SECRET_NAMES)
        and operator_reset_key_length_valid
    )
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
