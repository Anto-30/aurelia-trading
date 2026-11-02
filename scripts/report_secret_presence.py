from __future__ import annotations

import os


DERIV_CREDENTIAL_NAMES = (
    "DERIV_OAUTH_ACCESS_TOKEN",
    "DERIV_OAUTH_REFRESH_TOKEN",
    "DERIV_PAT",
    "DERIV_AUTH_TOKEN",
    "DERIV_REFRESH_TOKEN",
    "DERIV_APP_ID",
    "DERIV_EXPECTED_LOGINID",
    "DERIV_AUTHORIZED_ACCOUNT_ID",
    "DERIV_EXPECTED_CURRENCY",
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
    for name in DERIV_CREDENTIAL_NAMES:
        print(f"{name}_PRESENT={'true' if present(name) else 'false'}")

    oauth = os.getenv("DERIV_OAUTH_ACCESS_TOKEN", "").strip()
    pat = os.getenv("DERIV_PAT", "").strip()
    generic = os.getenv("DERIV_AUTH_TOKEN", "").strip()
    refresh = (
        os.getenv("DERIV_OAUTH_REFRESH_TOKEN", "").strip()
        or os.getenv("DERIV_REFRESH_TOKEN", "").strip()
    )
    tokens_equal = bool(oauth and pat and oauth == pat)
    credentials_isolated = not (
        pat or generic or refresh or tokens_equal
    )
    auth_mode = os.getenv("ACCOUNT_DERIV_AUTH_MODE", "none").strip().lower()
    mode_valid = auth_mode in {"none", "oauth"}

    print(f"ACCOUNT_DERIV_AUTH_MODE_VALID={'true' if mode_valid else 'false'}")
    print(f"DERIV_OAUTH_PAT_IDENTICAL={'true' if tokens_equal else 'false'}")
    print(f"DERIV_CREDENTIALS_ISOLATED_IN_PROCESS={'true' if credentials_isolated else 'false'}")
    print("DERIV_READ_ONLY_SCOPE_SUPPORTED=false")
    print("DERIV_AUTH_CONFIGURED=false")

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
    print("AURELIA_PRODUCTION_PREREQUISITES_CONFIGURED=false")
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    print("LIVE_EXECUTION=BLOCKED")
    print("CAPITAL_MOVEMENT_PERMITTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
