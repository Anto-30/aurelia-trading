from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from runtime.core.secrets import SecretsError, validate_secrets_at_startup


class RuntimeSecretModeTests(unittest.TestCase):
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

    def test_verify_only_runtime_rejects_unsealed_autonomous_flags(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "VERIFY_ONLY",
            "FINAL_EXECUTION_AUTHORIZATION": "false",
            "LIVE_EXECUTION": "BLOCKED",
            "AURELIA_AUTONOMOUS_LOOP": "true",
            "AURELIA_VERIFY_DERIV_AUTH": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SecretsError, "VERIFY_ONLY_RUNTIME_NOT_SEALED"):
                validate_secrets_at_startup()

    def test_pat_accepts_canonical_token_and_exact_real_account_binding(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "LIVE",
            "DERIV_AUTH_MODE": "pat",
            "DERIV_AUTH_TOKEN": "placeholder",
            "DERIV_APP_ID": "12345",
            "DERIV_EXPECTED_LOGINID": "CR123",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True):
            validate_secrets_at_startup()

    def test_pat_accepts_supported_aliases_but_still_requires_app_id(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "LIVE",
            "DERIV_AUTH_MODE": "pat",
            "DERIV_PAT": "placeholder",
            "DERIV_APP_ID": "12345",
            "DERIV_AUTHORIZED_ACCOUNT_ID": "CR123",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True):
            validate_secrets_at_startup()

    def test_oauth_accepts_token_alias_without_pat_app_id(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "LIVE",
            "DERIV_AUTH_MODE": "oauth",
            "DERIV_PAT": "placeholder-oauth-bearer",
            "DERIV_AUTHORIZED_ACCOUNT_ID": "CR123",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True):
            validate_secrets_at_startup()

    def test_pat_without_app_id_is_rejected(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "LIVE",
            "DERIV_AUTH_MODE": "pat",
            "DERIV_AUTH_TOKEN": "placeholder",
            "DERIV_EXPECTED_LOGINID": "CR123",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SecretsError, "DERIV_APP_ID"):
                validate_secrets_at_startup()

    def test_live_mode_rejects_demo_account_environment(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "LIVE",
            "DERIV_AUTH_MODE": "oauth",
            "DERIV_AUTH_TOKEN": "placeholder",
            "DERIV_EXPECTED_LOGINID": "CR123",
            "DERIV_EXPECTED_CURRENCY": "USD",
            "DERIV_ENVIRONMENT": "demo",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError, "LIVE_RUNTIME_REQUIRES_REAL_DERIV_ENVIRONMENT"
            ):
                validate_secrets_at_startup()

    def test_live_mode_requires_explicit_account_and_currency(self):
        env = {
            "AURELIA_DEPLOYMENT_MODE": "LIVE",
            "DERIV_AUTH_MODE": "oauth",
            "DERIV_AUTH_TOKEN": "placeholder",
            "DERIV_ENVIRONMENT": "real",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                SecretsError, "DERIV_EXPECTED_LOGINID_OR_DERIV_AUTHORIZED_ACCOUNT_ID"
            ):
                validate_secrets_at_startup()


if __name__ == "__main__":
    unittest.main()
