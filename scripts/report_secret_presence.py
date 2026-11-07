from __future__ import annotations

"""Report known policy state without reading any credential or secret value."""


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


def main() -> int:
    # This reporter intentionally does not inspect os.environ. Presence and
    # validity of protected secrets remain UNKNOWN unless an independently
    # approved, purpose-specific process is authorized to verify them.
    for name in DERIV_CREDENTIAL_NAMES:
        print(f"{name}_PRESENCE=NOT_INSPECTED")

    print("DERIV_ACCOUNT_EVIDENCE=BLOCKED")
    print("DERIV_ACCOUNT_BLOCK_REASON=DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE")
    print("DERIV_ACCOUNT_CREDENTIALS=NOT_INSPECTED")
    print("DERIV_READ_ONLY_SCOPE_SUPPORTED=false")
    print("DERIV_AUTH_CONFIGURED=false")

    for name in DEPLOYMENT_SECRET_NAMES:
        print(f"{name}_PRESENCE=NOT_INSPECTED")

    print("AURELIA_DEPLOYMENT_SECRET_STORE_CONFIGURED=UNKNOWN")
    print("AURELIA_PRODUCTION_PREREQUISITES_CONFIGURED=UNKNOWN")
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    print("LIVE_EXECUTION=BLOCKED")
    print("CAPITAL_MOVEMENT_PERMITTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
