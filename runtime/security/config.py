from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvironmentPolicy:
    name: str
    expected_account_type: str
    allows_real_credentials: bool

POLICIES = {
    "dev": EnvironmentPolicy("dev", "demo", False),
    "test": EnvironmentPolicy("test", "demo", False),
    "staging": EnvironmentPolicy("staging", "real", False),
    "production": EnvironmentPolicy("production", "real", True),
}

def credentials_allowed(environment: str, account_type: str) -> bool:
    policy = POLICIES.get(environment)
    return bool(policy and policy.allows_real_credentials and account_type == policy.expected_account_type)
