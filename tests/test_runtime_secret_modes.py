from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from runtime.core.secrets import (
    SecretsError,
    account_credential_keys_present,
    validate_secrets_at_startup,
)
from runtime.security.deriv_auth_gate import ACCOUNT_CREDENTIAL_ENV_NAMES
import runtime.core.secrets as secrets_module


class NoSecretValueReads(dict):
    def get(self, key, default=None):
        if key in ACCOUNT_CREDENTIAL_ENV_NAMES:
            raise AssertionError("account credential value must not be read")
        return super().get(key, default)


class RuntimeSecretModeTests(unittest.TestCase):
    def test_presence_check_uses_keys_without_reading_values(self):
        env = NoSecretValueReads({"DERIV_PAT": ""})
        self.assertTrue(account_credential_keys_present(env))
        self.assertFalse(account_credential_keys_present(NoSecretValueReads()))

    def test_verify_only_rejects_empty_credential_key_without_reading_value(self):
        env = NoSecretValueReads({
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "false",
            "DERIV_PAT": "",
        })
        with patch.object(secrets_module.os, "environ", env):
            with self.assertRaisesRegex(
                SecretsError,
                "VERIFY_ONLY_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED",
            ):
                validate_secrets_at_startup()

    def test_non_production_soak_rejects_empty_credential_key_without_reading_value(self):
        env = NoSecretValueReads({
            "AURELIA_NON_PRODUCTION_SOAK": "true",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_VERIFY_DERIV_PUBLIC": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "false",
            "AURELIA_CONTINUOUS_RUNTIME": "false",
            "DERIV_OAUTH_ACCESS_TOKEN": "",
        })
        with patch.object(secrets_module.os, "environ", env):
            with self.assertRaisesRegex(
                SecretsError,
                "NON_PRODUCTION_SOAK_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED",
            ):
                validate_secrets_at_startup()

    def test_non_production_soak_rejects_account_credentials(self):
        env = {
            "AURELIA_NON_PRODUCTION_SOAK": "true",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_VERIFY_DERIV_PUBLIC": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "false",
            "AURELIA_CONTINUOUS_RUNTIME": "false",
            "DERIV_PAT": "",
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
            "DERIV_OAUTH_ACCESS_TOKEN": "",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "VERIFY_ONLY_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED",
            ):
                validate_secrets_at_startup()

    def test_verify_only_auth_flag_rejects_credential_key_without_reading_value(self):
        env = NoSecretValueReads({
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "DERIV_OAUTH_ACCESS_TOKEN": "",
        })
        with patch.object(secrets_module.os, "environ", env):
            with self.assertRaisesRegex(
                SecretsError,
                "VERIFY_ONLY_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED",
            ):
                validate_secrets_at_startup()

    def test_verify_only_rejects_account_credential_keys_before_account_auth(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "",
            "DERIV_EXPECTED_LOGINID": "CR123",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "VERIFY_ONLY_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED",
            ):
                validate_secrets_at_startup()

    def test_verify_only_account_auth_blocks_without_read_only_scope(self):
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
                "VERIFY_ONLY_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED",
            ):
                validate_secrets_at_startup()

    def test_verify_only_account_auth_blocks_when_pat_is_present(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "",
            "DERIV_PAT": "",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SecretsError, "VERIFY_ONLY_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED"):
                validate_secrets_at_startup()

    def test_verify_only_account_auth_blocks_when_generic_token_is_present(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_AUTH_TOKEN": "",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "VERIFY_ONLY_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED",
            ):
                validate_secrets_at_startup()

    def test_verify_only_account_auth_blocks_without_comparing_credentials(self):
        marker = ""
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
            with self.assertRaisesRegex(SecretsError, "VERIFY_ONLY_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED"):
                validate_secrets_at_startup()

    def test_verify_only_account_auth_blocks_when_refresh_token_is_present(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "false",
            "AURELIA_VERIFY_DERIV_AUTH": "true",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "",
            "DERIV_OAUTH_REFRESH_TOKEN": "",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "VERIFY_ONLY_ACCOUNT_CREDENTIALS_MUST_NOT_BE_LOADED",
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
            "DERIV_PAT": "",
            "DERIV_EXPECTED_LOGINID": "CR123",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SecretsError, "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"):
                validate_secrets_at_startup()

    def test_live_startup_cannot_accept_distinct_oauth_without_read_scope(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "LIVE",
            "ACCOUNT_DERIV_AUTH_MODE": "oauth",
            "DERIV_OAUTH_ACCESS_TOKEN": "",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError,
                "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE",
            ):
                validate_secrets_at_startup()


if __name__ == "__main__":
    unittest.main()
