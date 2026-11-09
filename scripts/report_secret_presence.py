from __future__ import annotations

import os


DERIV_PRESENCE_FLAGS = {
    "DERIV_AUTH_TOKEN": "DERIV_AUTH_TOKEN_PRESENT",
    "DERIV_APP_ID": "DERIV_APP_ID_PRESENT",
    "DERIV_EXPECTED_LOGINID": "DERIV_EXPECTED_LOGINID_PRESENT",
    "DERIV_EXPECTED_CURRENCY": "DERIV_EXPECTED_CURRENCY_PRESENT",
}

DEPLOYMENT_PRESENCE_FLAGS = {
    "AURELIA_HOST": "AURELIA_HOST_PRESENT",
    "AURELIA_USER": "AURELIA_USER_PRESENT",
    "AURELIA_SSH_KEY": "AURELIA_SSH_KEY_PRESENT",
    "AURELIA_KNOWN_HOSTS": "AURELIA_KNOWN_HOSTS_PRESENT",
    "AURELIA_ATTESTATION_SIGNING_KEY": "AURELIA_ATTESTATION_SIGNING_KEY_PRESENT",
    "AURELIA_OPERATOR_RESET_SIGNING_KEY": "AURELIA_OPERATOR_RESET_SIGNING_KEY_PRESENT",
}


def flag(name: str) -> bool:
    """Read only a literal boolean supplied by GitHub expression evaluation."""
    return os.getenv(name, "false").strip().lower() == "true"


def main() -> int:
    # GitHub expressions evaluate secret presence to booleans. No secret value,
    # token, host key, or signing key is placed in this process environment.
    for display_name, env_name in DERIV_PRESENCE_FLAGS.items():
        print(f"{display_name}_PRESENT={str(flag(env_name)).lower()}")

    auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower() or "pat"
    auth_mode_valid = auth_mode in {"pat", "oauth"}
    currency_supported = flag("DERIV_EXPECTED_CURRENCY_SUPPORTED")
    environment = os.getenv("DERIV_ENVIRONMENT", "real").strip().lower() or "real"
    environment_valid = environment in {"real", "demo"}

    # The presence of a trade-scoped token does not constitute an approved
    # account verifier. Deriv's required account-list/OTP endpoints are trade
    # scoped and no read-only account scope is currently documented.
    deriv_configured = False
    print(f"DERIV_AUTH_MODE_VALID={str(auth_mode_valid).lower()}")
    print(f"DERIV_AUTH_MODE_EFFECTIVE={auth_mode.upper() if auth_mode_valid else 'INVALID'}")
    print(f"DERIV_EXPECTED_CURRENCY_SUPPORTED={str(currency_supported).lower()}")
    print(f"DERIV_ENVIRONMENT_VALID={str(environment_valid).lower()}")
    print(f"DERIV_ENVIRONMENT_EFFECTIVE={environment.upper() if environment_valid else 'INVALID'}")
    print("DERIV_READ_ONLY_ACCOUNT_SCOPE_AVAILABLE=false")
    print(f"DERIV_AUTH_CONFIGURED={str(deriv_configured).lower()}")

    deployment_flags = {
        display_name: flag(env_name)
        for display_name, env_name in DEPLOYMENT_PRESENCE_FLAGS.items()
    }
    for name, is_present in deployment_flags.items():
        print(f"{name}_PRESENT={str(is_present).lower()}")

    # Presence-only metadata cannot establish cryptographic key strength.
    # The runtime verifier must validate length/format without echoing values.
    print("AURELIA_OPERATOR_RESET_SIGNING_KEY_LENGTH_VALID=UNVERIFIED")
    print("AURELIA_DEPLOYMENT_SECRET_STORE_CONFIGURED=false")
    print("AURELIA_PRODUCTION_PREREQUISITES_CONFIGURED=false")
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    print("LIVE_EXECUTION=BLOCKED")
    print("CAPITAL_MOVEMENT_PERMITTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
