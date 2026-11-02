from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from runtime.core.secrets import SecretsError, validate_secrets_at_startup


class RuntimeSecretModeTests(unittest.TestCase):
    def test_non_production_soak_rejects_account_credentials(self):
        env = {
            "AURELIA_NON_PRODUCTION_SOAK": "true",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_VERIFY_DERIV_PUBLIC": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "false",
            "AURELIA_CONTINUOUS_RUNTIME": "false",
            "DERIV_PAT": "UNEXPECTED_PAT_SENTINEL",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "NON_PRODUCTION_SOAK_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED",
            ):
                validate_secrets_at_startup()

    def test_locked_verify_only_runtime_can_start_without_broker_credentials(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            validate_secrets_at_startup()

    def test_verify_only_rejects_account_credentials_when_account_auth_is_disabled(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "false",
            "DERIV_OAUTH_ACCESS_TOKEN": "UNEXPECTED_OAUTH_SENTINEL",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "VERIFY_ONLY_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED",
            ):
                validate_secrets_at_startup()

    def test_verify_only_account_auth_is_blocked_even_with_distinct_oauth(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SENTINEL",
            "DERIV_EXPECTED_LOGINID": "CR123",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            ):
                validate_secrets_at_startup()

    def test_verify_only_read_only_auth_fails_without_credentials(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "DERIV_OAUTH_ACCESS_TOKEN_MISSING",
            ):
                validate_secrets_at_startup()

    def test_verify_only_rejects_pat_even_if_oauth_is_selected(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SENTINEL",
            "DERIV_PAT": "PAT_SENTINEL",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SecretsError, "ACCOUNT_PLANE_PAT_PRESENT"):
                validate_secrets_at_startup()

    def test_verify_only_rejects_generic_token_fallback(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_AUTH_TOKEN": "GENERIC_SENTINEL",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "GENERIC_TOKEN_FALLBACK_BLOCKED",
            ):
                validate_secrets_at_startup()

    def test_verify_only_rejects_identical_oauth_and_pat(self):
        marker = "SAME_SECRET_SENTINEL"
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": marker,
            "DERIV_PAT": marker,
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SecretsError, "OAUTH_TOKEN_EQUALS_PAT"):
                validate_secrets_at_startup()

    def test_verify_only_rejects_unsupported_refresh_token(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SENTINEL",
            "DERIV_OAUTH_REFRESH_TOKEN": "REFRESH_SENTINEL",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "DERIV_OAUTH_REFRESH_TOKEN_UNSUPPORTED",
            ):
                validate_secrets_at_startup()

    def test_verify_only_runtime_rejects_unsealed_autonomous_flags(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "true",
            "AURELIA_VERIFY_DERIV_AUTH": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "VERIFY_ONLY_RUNTIME_NOT_SEALED",
            ):
                validate_secrets_at_startup()

    def test_live_startup_never_accepts_pat_or_legacy_token(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "LIVE",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_PAT": "PAT_SENTINEL",
            "DERIV_EXPECTED_LOGINID": "CR123",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SecretsError, "ACCOUNT_PLANE_PAT_PRESENT"):
                validate_secrets_at_startup()

    def test_live_startup_cannot_accept_distinct_oauth_without_read_scope(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "LIVE",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "OAUTH_SENTINEL",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            ):
                validate_secrets_at_startup()


if __name__ == "__main__":
    unittest.main()
