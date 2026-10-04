from __future__ import annotations

import os


SECRET_NAMES = (
    "DERIV_AUTH_TOKEN",
    "DERIV_APP_ID",
    "DERIV_EXPECTED_LOGINID",
    "DERIV_EXPECTED_CURRENCY",
    "RAILWAY_TOKEN",
)


def present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def main() -> int:
    for name in SECRET_NAMES:
        print(f"{name}_PRESENT={'true' if present(name) else 'false'}")

    auth_mode = os.getenv("DERIV_AUTH_MODE", "pat").strip().lower() or "pat"
    deriv_core = all(
        present(name)
        for name in (
            "DERIV_AUTH_TOKEN",
            "DERIV_EXPECTED_LOGINID",
            "DERIV_EXPECTED_CURRENCY",
        )
    )
    deriv_configured = deriv_core and (
        auth_mode != "pat" or present("DERIV_APP_ID")
    )

    print(f"DERIV_AUTH_CONFIGURED={'true' if deriv_configured else 'false'}")
    print("FINAL_EXECUTION_AUTHORIZATION=false")
    print("LIVE_EXECUTION=BLOCKED")
    print("CAPITAL_MOVEMENT_PERMITTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
