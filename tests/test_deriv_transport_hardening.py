from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from runtime.adapters.deriv_adapter import DerivAdapter, DerivProtocolError
from runtime.adapters.deriv_session import DerivSessionError, get_authenticated_ws_url
from runtime.adapters.deriv_ws import DerivTransportError, DerivWebSocketTransport


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


    async def test_unexpected_connect_failure_closes_transport_and_fails_closed(self):
        transport = SimpleNamespace(
            connect=AsyncMock(),
            request=AsyncMock(side_effect=ValueError("malformed reply")),
            close=AsyncMock(),
        )
        adapter = DerivAdapter(
            ws_url="wss://api.derivws.com/trading/v1/options/ws/real",
            auth_token="test-token",
            expected_loginid="CRREAL",
            expected_currency="USD",
        )
        with patch("runtime.adapters.deriv_adapter.DerivWebSocketTransport", return_value=transport):
            with self.assertRaisesRegex(ValueError, "malformed reply"):
                await adapter.connect()
        transport.close.assert_awaited_once()
        self.assertFalse(adapter.authorized)
        self.assertIsNone(adapter.account)

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


    async def test_reader_failure_closes_socket_before_dropping_reference(self):
        reader_started = asyncio.Event()

        async def failing_recv():
            reader_started.set()
            raise RuntimeError("synthetic socket read failure")

        socket = SimpleNamespace(
            recv=AsyncMock(side_effect=failing_recv),
            close=AsyncMock(),
        )
        transport = DerivWebSocketTransport(
            "wss://api.derivws.com/trading/v1/options/ws/real"
        )
        transport.ws = socket
        transport._reader_task = asyncio.create_task(transport._reader_loop())
        await asyncio.wait_for(reader_started.wait(), timeout=1.0)
        await asyncio.wait_for(transport._reader_task, timeout=1.0)

        socket.close.assert_awaited_once()
        self.assertIsNone(transport.ws)

    async def test_close_wakes_blocked_subscription_and_clears_registry(self):
        reader_started = asyncio.Event()
        subscribe_sent = asyncio.Event()
        wait_forever = asyncio.Event()

        async def blocking_recv():
            reader_started.set()
            await wait_forever.wait()
            return "{}"

        async def send(message):
            if '"subscribe": 1' in message:
                subscribe_sent.set()

        socket = SimpleNamespace(
            recv=AsyncMock(side_effect=blocking_recv),
            send=AsyncMock(side_effect=send),
            close=AsyncMock(),
        )
        transport = DerivWebSocketTransport(
            "wss://api.derivws.com/trading/v1/options/ws/real"
        )
        transport.ws = socket
        transport._reader_task = asyncio.create_task(transport._reader_loop())
        await asyncio.wait_for(reader_started.wait(), timeout=1.0)

        stream = transport.subscribe("ticks:R_100", {"ticks": "R_100"})
        consumer = asyncio.create_task(stream.__anext__())
        await asyncio.wait_for(subscribe_sent.wait(), timeout=1.0)
        self.assertIn("ticks:R_100", transport._subscriptions)

        await transport.close()
        with self.assertRaisesRegex(DerivTransportError, "BROKER_SESSION_CLOSED"):
            await asyncio.wait_for(consumer, timeout=1.0)

        self.assertEqual(transport._subscriptions, {})
        self.assertEqual(transport._subscription_by_request_id, {})
        socket.close.assert_awaited_once()

    async def test_reconnect_preserves_and_rebinds_active_subscription(self):
        first_reader_started = asyncio.Event()
        second_reader_started = asyncio.Event()
        first_send = asyncio.Event()
        second_send = asyncio.Event()
        wait_forever = asyncio.Event()

        def make_socket(reader_started, subscribe_sent):
            async def blocking_recv():
                reader_started.set()
                await wait_forever.wait()
                return "{}"

            async def send(message):
                if '"subscribe": 1' in message:
                    subscribe_sent.set()

            return SimpleNamespace(
                recv=AsyncMock(side_effect=blocking_recv),
                send=AsyncMock(side_effect=send),
                close=AsyncMock(),
            )

        first_socket = make_socket(first_reader_started, first_send)
        second_socket = make_socket(second_reader_started, second_send)
        transport = DerivWebSocketTransport(
            "wss://api.derivws.com/trading/v1/options/ws/real"
        )
        with patch("runtime.adapters.deriv_ws.connect", new=AsyncMock(side_effect=[first_socket, second_socket])):
            await transport.connect()
            await asyncio.wait_for(first_reader_started.wait(), timeout=1.0)
            stream = transport.subscribe("ticks:R_100", {"ticks": "R_100"})
            consumer = asyncio.create_task(stream.__anext__())
            await asyncio.wait_for(first_send.wait(), timeout=1.0)
            old_id = transport._subscriptions["ticks:R_100"].request_id

            await transport.reconnect(
                "wss://api.derivws.com/trading/v1/options/ws/real?otp=fresh"
            )

            await asyncio.wait_for(second_reader_started.wait(), timeout=1.0)
            await asyncio.wait_for(second_send.wait(), timeout=1.0)
            new_subscription = transport._subscriptions["ticks:R_100"]
            self.assertNotEqual(new_subscription.request_id, old_id)
            self.assertEqual(
                transport._subscription_by_request_id[new_subscription.request_id],
                "ticks:R_100",
            )
            self.assertEqual(new_subscription.payload["ticks"], "R_100")

            await transport.close()
            with self.assertRaisesRegex(DerivTransportError, "BROKER_SESSION_CLOSED"):
                await asyncio.wait_for(consumer, timeout=1.0)


if __name__ == "__main__":
    unittest.main()
