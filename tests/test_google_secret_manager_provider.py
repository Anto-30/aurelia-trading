from __future__ import annotations

import os
import sys
import types
import unittest
from unittest.mock import patch

from runtime.core.secrets import (
    SecretsError,
    _read_google_secret,
    get_optional_secret,
)


class GoogleSecretManagerProviderTests(unittest.TestCase):
    def tearDown(self):
        _read_google_secret.cache_clear()

    def test_default_provider_preserves_environment_for_nonproduction_tests(self):
        with patch.dict(os.environ, {"DERIV_AUTH_TOKEN": "test-value"}, clear=True):
            self.assertEqual(get_optional_secret("DERIV_AUTH_TOKEN"), "test-value")

    def test_explicit_gsm_provider_never_falls_back_to_environment(self):
        env = {
            "AURELIA_SECRET_PROVIDER": "google_secret_manager",
            "DERIV_AUTH_TOKEN": "must-not-be-used",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(SecretsError, "GOOGLE_SECRET_MANAGER_CONFIGURATION_MISSING"):
                get_optional_secret("DERIV_AUTH_TOKEN")

    def test_gsm_rejects_latest_alias_to_pin_production_secret_version(self):
        with self.assertRaisesRegex(SecretsError, "VERSION_MUST_BE_NUMERIC"):
            _read_google_secret("project", "deriv-auth-token", "latest")

    def test_gsm_reads_explicit_version_and_returns_secret_value(self):
        class FakeClient:
            def access_secret_version(self, request):
                self.request = request
                return types.SimpleNamespace(
                    payload=types.SimpleNamespace(data=b"unit-test-token")
                )

        fake_secretmanager = types.ModuleType("google.cloud.secretmanager")
        fake_secretmanager.SecretManagerServiceClient = FakeClient
        fake_google = types.ModuleType("google")
        fake_cloud = types.ModuleType("google.cloud")
        fake_google.__path__ = []
        fake_cloud.__path__ = []
        fake_google.cloud = fake_cloud
        fake_cloud.secretmanager = fake_secretmanager
        with patch.dict(
            sys.modules,
            {
                "google": fake_google,
                "google.cloud": fake_cloud,
                "google.cloud.secretmanager": fake_secretmanager,
            },
        ):
            self.assertEqual(
                _read_google_secret("project", "deriv-auth-token", "7"),
                "unit-test-token",
            )

    def test_gsm_error_does_not_leak_provider_exception_text(self):
        fake_secretmanager = types.ModuleType("google.cloud.secretmanager")

        class BrokenClient:
            def access_secret_version(self, request):
                raise RuntimeError("do-not-leak-this-detail")

        fake_secretmanager.SecretManagerServiceClient = BrokenClient
        fake_google = types.ModuleType("google")
        fake_cloud = types.ModuleType("google.cloud")
        fake_google.__path__ = []
        fake_cloud.__path__ = []
        fake_google.cloud = fake_cloud
        fake_cloud.secretmanager = fake_secretmanager
        with patch.dict(
            sys.modules,
            {
                "google": fake_google,
                "google.cloud": fake_cloud,
                "google.cloud.secretmanager": fake_secretmanager,
            },
        ):
            with self.assertRaisesRegex(SecretsError, "GOOGLE_SECRET_MANAGER_ACCESS_FAILED") as ctx:
                _read_google_secret("project", "deriv-auth-token", "8")
            self.assertNotIn("do-not-leak-this-detail", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
