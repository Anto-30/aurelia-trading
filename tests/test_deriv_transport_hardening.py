from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from runtime.adapters.deriv_adapter import DerivAdapter, DerivProtocolError
from runtime.adapters.deriv_session import DerivSessionError, get_authenticated_ws_url
from runtime.adapters.deriv_ws import DerivWebSocketTransport


class DerivAdapterHardeningTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_fails_before_network_when_expected_loginid_missing(self):
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/real",
            expected_currency="USD",
        )
        with patch("runtime.adapters.deriv_adapter.DerivWebSocketTransport") as factory:
            with self.assertRaisesRegex(
                DerivProtocolError, "EXPECTED_ACCOUNT_LOGINID_REQUIRED"
            ):
                await adapter.connect()
            factory.assert_not_called()

    async def test_otp_account_id_becomes_explicit_account_binding(self):
        url = "wss://api.derivws.com/trading/v1/options/ws/real?otp=test-only"
        transport = SimpleNamespace(
            connect=AsyncMock(),
            request=AsyncMock(return_value={
                "req_id": 1,
                "balance": {
                    "loginid": "CR12345",
                    "currency": "USD",
                    "balance": 100.0,
                },
            }),
            close=AsyncMock(),
        )
        adapter = DerivAdapter(expected_currency="USD")
        with (
            patch(
                "runtime.adapters.deriv_adapter.get_authenticated_ws_url",
                return_value=SimpleNamespace(url=url),
            ),
            patch(
                "runtime.adapters.deriv_adapter.DerivWebSocketTransport",
                return_value=transport,
            ),
        ):
            account = await adapter.connect_from_otp("CR12345")
        self.assertEqual(account.loginid, "CR12345")
        self.assertEqual(adapter.expected_loginid, "CR12345")
        self.assertTrue(adapter.authorized)

    async def test_configured_account_mismatch_rejected_before_otp_request(self):
        adapter = DerivAdapter(expected_loginid="CRREAL", expected_currency="USD")
        with patch("runtime.adapters.deriv_adapter.get_authenticated_ws_url") as otp:
            with self.assertRaisesRegex(DerivProtocolError, "ACCOUNT_IDENTITY_MISMATCH"):
                await adapter.connect_from_otp("CROTHER")
            otp.assert_not_called()

    async def test_proposal_opcode_cannot_be_overridden_by_parameters(self):
        adapter = DerivAdapter(ws_url="wss://api.derivws.com/trading/v1/options/ws/real")
        adapter.request = AsyncMock(return_value={"proposal": {"id": "proposal-demo"}})
        proposal_id = await adapter.request_proposal({
            "contract_type": "CALL",
            "currency": "USD",
            "underlying_symbol": "R_100",
            "proposal": 0,
        })
        self.assertEqual(proposal_id, "proposal-demo")
        payload = adapter.request.await_args.args[0]
        self.assertEqual(payload["proposal"], 1)


class DerivSessionInputTests(unittest.TestCase):
    def test_account_id_path_delimiters_are_rejected_before_http_request(self):
        invalid_ids = ("../real", "DOT12345?otp=evil", "DOT12345#fragment", "DOT/12345")
        with patch("runtime.adapters.deriv_session.urlopen") as http:
            for account_id in invalid_ids:
                with self.subTest(account_id=account_id):
                    with self.assertRaisesRegex(DerivSessionError, "ACCOUNT_ID_INVALID"):
                        get_authenticated_ws_url(
                            account_id, bearer_token="test-token", app_id="12345"
                        )
            http.assert_not_called()


class DerivTransportShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_socket_after_reader_finally_clears_self_ws(self):
        reader_started = asyncio.Event()
        wait_forever = asyncio.Event()

        async def blocking_recv():
            reader_started.set()
            await wait_forever.wait()
            return "{}"

        socket = SimpleNamespace(
            recv=AsyncMock(side_effect=blocking_recv),
            close=AsyncMock(),
        )
        transport = DerivWebSocketTransport(
            "wss://api.derivws.com/trading/v1/options/ws/real"
        )
        transport.ws = socket
        transport._reader_task = asyncio.create_task(transport._reader_loop())
        await asyncio.wait_for(reader_started.wait(), timeout=1.0)

        await transport.close()

        socket.close.assert_awaited_once()
        self.assertIsNone(transport.ws)
        self.assertIsNone(transport._reader_task)
        self.assertEqual(transport._subscription_by_request_id, {})


if __name__ == "__main__":
    unittest.main()
