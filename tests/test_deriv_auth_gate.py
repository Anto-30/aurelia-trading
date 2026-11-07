from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from research.utils.deriv_auth_gate import (
    PUBLIC_RESEARCH_WS_URL,
    ACCOUNT_CREDENTIAL_ENV_NAMES,
    DerivAuthenticationGate,
    SecurityError,
)


class DerivAuthenticationGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_research_client_uses_public_endpoint_without_auth_arguments(self):
        gate = DerivAuthenticationGate(plane="research", environ={})
        client = gate.get_client()
        self.assertEqual(client.endpoint, PUBLIC_RESEARCH_WS_URL)
        self.assertEqual(
            client.endpoint,
            "wss://api.derivws.com/trading/v1/options/ws/public",
        )
        self.assertNotIn("app_id=", client.endpoint)

        fake_transport = type(
            "FakeTransport",
            (),
            {
                "connect": AsyncMock(),
                "request": AsyncMock(return_value={"candles": [{"epoch": 1, "open": "1", "high": "2", "low": "1", "close": "2"}]}),
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
            candles = await client.historical_candles(
                "R_100",
                granularity=60,
                count=10,
                end="latest",
            )
            self.assertEqual(len(candles), 1)
            sent_payload = fake_transport.request.await_args.args[0]
            self.assertEqual(sent_payload["ticks_history"], "R_100")
            self.assertEqual(sent_payload["granularity"], 60)
            self.assertEqual(sent_payload["style"], "candles")
            self.assertEqual(set(transport_factory.call_args.kwargs), {"timeout_seconds"})
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

    def test_research_plane_rechecks_credentials_at_request_time(self):
        environ = {}
        client = DerivAuthenticationGate(plane="research", environ=environ).get_client()
        environ["DERIV_PAT"] = "late_injected_pat"
        with self.assertRaisesRegex(
            SecurityError,
            "RESEARCH_PLANE_ACCOUNT_CREDENTIALS_PRESENT",
        ):
            client.validate_request({"ticks_history": "R_100"})

    def test_public_contract_proposal_quotes_are_disabled_by_policy(self):
        client = DerivAuthenticationGate(plane="research", environ={}).get_client()
        with self.assertRaisesRegex(
            SecurityError,
            "PUBLIC_RESEARCH_ACTION_NOT_ALLOWED",
        ):
            client.validate_request({
                "proposal": 1,
                "amount": 1.0,
                "basis": "stake",
                "contract_type": "CALL",
                "currency": "USD",
                "duration": 10,
                "duration_unit": "t",
                "underlying_symbol": "R_100",
            })

    def test_public_proposal_rejects_unknown_or_capital_moving_fields(self):
        client = DerivAuthenticationGate(plane="research", environ={}).get_client()
        with self.assertRaisesRegex(SecurityError, "PUBLIC_RESEARCH_REQUEST_FIELD_NOT_ALLOWED"):
            client.validate_request({
                "proposal": 1,
                "amount": 1.0,
                "buy": "proposal-id",
            })

    def test_research_plane_does_not_accept_capital_moving_actions(self):
        client = DerivAuthenticationGate(plane="research", environ={}).get_client()
        with self.assertRaisesRegex(SecurityError, "PUBLIC_RESEARCH_ACTION_NOT_ALLOWED"):
            client.validate_request({"buy": "proposal-id", "price": 1})

    def test_account_plane_always_blocks_without_reading_environment_values(self):
        class UnreadableEnvironment:
            def get(self, key, default=None):
                raise AssertionError("account gate must not read environment values")

            def __contains__(self, key):
                raise AssertionError("account gate must not inspect credential presence")

        with self.assertRaisesRegex(SecurityError, "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"):
            DerivAuthenticationGate(
                plane="account",
                environ=UnreadableEnvironment(),
            ).get_client()

    def test_account_plane_blocks_all_auth_modes_and_credential_shapes(self):
        environments = (
            {},
            {"ACCOUNT_DERIV_AUTH_MODE": "none"},
            {"ACCOUNT_DERIV_AUTH_MODE": "pat", "DERIV_PAT": "test-sentinel"},
            {"ACCOUNT_DERIV_AUTH_MODE": "oauth", "DERIV_OAUTH_ACCESS_TOKEN": "test-sentinel"},
            {"ACCOUNT_DERIV_AUTH_MODE": "oauth", "DERIV_AUTH_TOKEN": "test-sentinel"},
        )
        for environ in environments:
            with self.subTest(keys=tuple(environ)):
                with self.assertRaisesRegex(SecurityError, "DERIV_READ_ONLY_ACCOUNT_SCOPE_UNAVAILABLE"):
                    DerivAuthenticationGate(plane="account", environ=environ).get_client()

    def test_public_client_rejects_empty_account_credential_keys(self):
        for name in ACCOUNT_CREDENTIAL_ENV_NAMES:
            with self.subTest(name=name):
                with self.assertRaisesRegex(SecurityError, "RESEARCH_PLANE_ACCOUNT_CREDENTIALS_PRESENT"):
                    DerivAuthenticationGate(
                        plane="research",
                        environ={name: ""},
                    ).get_client()

    def test_unknown_plane_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_DERIV_AUTH_PLANE"):
            DerivAuthenticationGate(plane="live", environ={}).get_client()


if __name__ == "__main__":
    unittest.main()
