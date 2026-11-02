from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from research.utils.deriv_auth_gate import (
    PUBLIC_RESEARCH_WS_URL,
    AuthModeMismatchError,
    DerivAuthenticationGate,
    SecurityError,
)


class DerivAuthenticationGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_research_client_uses_public_endpoint_without_auth_arguments(self):
        gate = DerivAuthenticationGate(plane="research", environ={})
        client = gate.get_client()
        self.assertEqual(client.endpoint, PUBLIC_RESEARCH_WS_URL)

        fake_transport = type(
            "FakeTransport",
            (),
            {
                "connect": AsyncMock(),
                "request": AsyncMock(return_value={"history": {"prices": []}}),
                "subscribe": lambda self, key, payload: iter(()),
                "close": AsyncMock(),
            },
        )()

        with patch(
            "research.utils.deriv_auth_gate.DerivWebSocketTransport",
            return_value=fake_transport,
        ) as transport_factory:
            await client.connect()
            transport_factory.assert_called_once_with(
                PUBLIC_RESEARCH_WS_URL,
                timeout_seconds=10.0,
            )
            await client.request({
                "ticks_history": "R_100",
                "start": 1,
                "end": "latest",
                "style": "candles",
                "granularity": 60,
            })
            fake_transport.request.assert_awaited_once()
            await client.close()

    def test_research_plane_rejects_any_account_credential_in_environment(self):
        for name in (
            "DERIV_AUTH_TOKEN",
            "DERIV_PAT",
            "DERIV_OAUTH_ACCESS_TOKEN",
            "DERIV_OAUTH_REFRESH_TOKEN",
            "DERIV_REFRESH_TOKEN",
        ):
            with self.subTest(name=name):
                with self.assertRaisesRegex(SecurityError, "RESEARCH_PLANE_ACCOUNT_CREDENTIALS_PRESENT"):
                    DerivAuthenticationGate(
                        plane="research",
                        environ={name: "secret-sentinel"},
                    ).get_client()

    def test_research_plane_does_not_accept_capital_moving_actions(self):
        client = DerivAuthenticationGate(plane="research", environ={}).get_client()
        with self.assertRaisesRegex(SecurityError, "PUBLIC_RESEARCH_ACTION_NOT_ALLOWED"):
            client.validate_request({"buy": "proposal-id", "price": 1})

    def test_identical_oauth_and_pat_values_are_a_critical_security_error(self):
        with self.assertRaisesRegex(SecurityError, "OAUTH_TOKEN_EQUALS_PAT"):
            DerivAuthenticationGate(
                plane="account",
                environ={
                    "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                    "DERIV_OAUTH_ACCESS_TOKEN": "same-secret",
                    "DERIV_PAT": "same-secret",
                },
            ).get_client()

    def test_account_plane_rejects_pat_even_if_value_differs(self):
        with self.assertRaisesRegex(SecurityError, "ACCOUNT_PLANE_PAT_PRESENT"):
            DerivAuthenticationGate(
                plane="account",
                environ={
                    "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                    "DERIV_OAUTH_ACCESS_TOKEN": "oauth-secret",
                    "DERIV_PAT": "different-pat",
                },
            ).get_client()

    def test_account_plane_rejects_legacy_generic_token_fallback(self):
        with self.assertRaisesRegex(AuthModeMismatchError, "GENERIC_TOKEN_FALLBACK_BLOCKED"):
            DerivAuthenticationGate(
                plane="account",
                environ={
                    "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                    "DERIV_AUTH_TOKEN": "ambiguous-token",
                },
            ).get_client()

    def test_account_plane_fails_closed_when_read_only_scope_is_unavailable(self):
        with self.assertRaisesRegex(SecurityError, "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"):
            DerivAuthenticationGate(
                plane="account",
                environ={
                    "ACCOUNT_DERIV_AUTH_MODE": "oauth",
                    "DERIV_OAUTH_ACCESS_TOKEN": "oauth-secret",
                },
            ).get_client()

    def test_unknown_plane_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_DERIV_AUTH_PLANE"):
            DerivAuthenticationGate(plane="live", environ={}).get_client()


if __name__ == "__main__":
    unittest.main()
