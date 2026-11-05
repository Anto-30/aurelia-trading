from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from runtime.adapters.deriv_adapter import DerivAdapter
from runtime.adapters.deriv_session import AuthenticatedWebSocketUrl
from runtime.adapters.session_manager import (
    DerivAccountBinding,
    DerivSessionManager,
)
from runtime.adapters.deriv_ws import DerivWebSocketTransport

LOGIN_ID = "CRREAL"
BROKER_UUID = "f2ac691f-68d7-b467-6308-72d5ecaf9030"
ACCOUNT_ID = LOGIN_ID


class FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class FakeSessionManager:
    """Provides two different OTP URLs without contacting Deriv."""

    def __init__(self):
        self.calls = 0

    def bootstrap(self, *, bearer_token=None, app_id=None):
        self.calls += 1
        otp = "ONE" if self.calls == 1 else "TWO"
        binding = DerivAccountBinding(
            loginid=ACCOUNT_ID,
            account_type="real",
            currency="USD",
            environment="real",
            account_id=ACCOUNT_ID,
            status="active",
            source_endpoint="https://api.derivws.com/trading/v1/options/accounts",
            source_response_sha256="a" * 64,
            observed_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        return SimpleNamespace(
            binding=binding,
            websocket=AuthenticatedWebSocketUrl(
                account_id=ACCOUNT_ID,
                url=f"wss://api.derivws.com/trading/v1/options/ws/real?otp={otp}",
            ),
        )


class FakeTransport:
    """In-memory transport. It records API actions and simulates reconnects."""

    instances = []

    def __init__(self, url, *, timeout_seconds=10.0):
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.connected = False
        self.closed = False
        self.request_id = 0
        self.actions = []
        self.reconnect_urls = []
        self.ping_count = 0
        self.close_count = 0
        self.__class__.instances.append(self)

    async def connect(self):
        self.connected = True
        self.closed = False

    def allocate_request_id(self):
        self.request_id += 1
        return self.request_id

    def reserve_request_id(self, request_id):
        self.request_id = max(self.request_id, request_id)

    async def request(self, payload):
        if not self.connected or self.closed:
            raise RuntimeError("FAKE_TRANSPORT_NOT_CONNECTED")
        action = next(key for key in payload if key != "req_id")
        self.actions.append(action)
        req_id = payload["req_id"]
        if action == "balance":
            body = {
                "balance": {
                    "balance": 100.0,
                    "currency": "USD",
                    "id": BROKER_UUID,
                    "loginid": LOGIN_ID,
                }
            }
        elif action == "portfolio":
            body = {"portfolio": {"contracts": []}}
        elif action == "statement":
            body = {"statement": {"transactions": []}}
        else:
            raise AssertionError(f"Unexpected read-only request: {action}")
        return {"req_id": req_id, **body}

    async def ping(self):
        if not self.connected or self.closed:
            raise RuntimeError("FAKE_TRANSPORT_NOT_CONNECTED")
        self.ping_count += 1
        return 0.25

    async def reconnect(self, fresh_url=None):
        if not fresh_url:
            raise RuntimeError("FRESH_AUTHENTICATED_WS_URL_REQUIRED")
        self.reconnect_urls.append(fresh_url)
        await self.close()
        self.url = fresh_url
        await self.connect()

    async def close(self):
        self.close_count += 1
        self.connected = False
        self.closed = True


class FakeWebSocket:
    def __init__(self):
        self.closed = False
        self.ping_count = 0

    async def recv(self):
        await asyncio.Future()

    async def ping(self):
        self.ping_count += 1
        return asyncio.sleep(0)

    async def close(self):
        self.closed = True


class DerivReadOnlyLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        FakeTransport.instances.clear()

    async def test_rest_account_list_and_fresh_otp_bootstrap_are_separate(self):
        accounts_response = FakeResponse({
            "data": [{
                "account_id": ACCOUNT_ID,
                "account_type": "real",
                "currency": "USD",
                "status": "active",
            }]
        })
        otp_response = FakeResponse({
            "data": {
                "url": "wss://api.derivws.com/trading/v1/options/ws/real?otp=MOCK-ONE-TIME"
            }
        })
        manager = DerivSessionManager(
            expected_loginid=ACCOUNT_ID,
            expected_environment="real",
            expected_currency="USD",
        )

        with (
            patch("runtime.adapters.session_manager.urlopen", return_value=accounts_response) as rest_call,
            patch("runtime.adapters.deriv_session.urlopen", return_value=otp_response) as otp_call,
        ):
            bootstrap = manager.bootstrap(bearer_token="TEST_ONLY_TOKEN", app_id="12345")

        self.assertEqual(bootstrap.binding.account_id, ACCOUNT_ID)
        self.assertEqual(bootstrap.binding.status, "active")
        self.assertEqual(bootstrap.binding.currency, "USD")
        self.assertEqual(bootstrap.websocket.account_id, ACCOUNT_ID)
        self.assertEqual(
            bootstrap.websocket.safe_url(),
            "wss://api.derivws.com/trading/v1/options/ws/real",
        )
        self.assertEqual(rest_call.call_args.args[0].get_method(), "GET")
        self.assertIn("/trading/v1/options/accounts", rest_call.call_args.args[0].full_url)
        self.assertEqual(otp_call.call_args.args[0].get_method(), "POST")
        self.assertIn(f"/accounts/{ACCOUNT_ID}/otp", otp_call.call_args.args[0].full_url)
        self.assertTrue(rest_call.call_args.args[0].has_header("Authorization"))
        self.assertTrue(otp_call.call_args.args[0].has_header("Authorization"))

    async def test_complete_mocked_read_only_lifecycle_reconnects_and_reconciles(self):
        manager = FakeSessionManager()
        first = manager.bootstrap(bearer_token="TEST_ONLY_TOKEN", app_id="12345")
        adapter = DerivAdapter(
            ws_url=first.websocket.url,
            expected_loginid=ACCOUNT_ID,
            expected_currency="USD",
            environment="real",
            auth_token="",
        )

        with patch(
            "runtime.adapters.deriv_adapter.DerivWebSocketTransport",
            FakeTransport,
        ):
            account = await adapter.connect()
            transport = adapter.transport
            self.assertEqual(account.loginid, ACCOUNT_ID)
            self.assertEqual(account.broker_uuid, BROKER_UUID)

            # WebSocket control-frame heartbeat; no Deriv account API call.
            heartbeat_ms = await transport.ping()
            self.assertGreaterEqual(heartbeat_ms, 0.0)

            # Initial broker-state observation.
            before_balance = await adapter.get_balance()
            before_portfolio = await adapter.portfolio()
            before_statement = await adapter.statement(limit=100)
            after_balance = await adapter.get_balance()
            self.assertEqual(before_balance.balance, after_balance.balance)
            self.assertEqual(before_portfolio, [])
            self.assertEqual(before_statement, [])

            # Controlled disconnect, then request a genuinely fresh OTP URL.
            await transport.close()
            second = manager.bootstrap(bearer_token="TEST_ONLY_TOKEN", app_id="12345")
            await adapter.reconnect(second.websocket.url)

            # Recovery/reconciliation after re-authenticated reconnect.
            recovered_balance = await adapter.get_balance()
            recovered_portfolio = await adapter.portfolio()
            recovered_statement = await adapter.statement(limit=100)
            self.assertEqual(recovered_balance.balance, after_balance.balance)
            self.assertEqual(recovered_balance.account, account)
            self.assertEqual(recovered_portfolio, before_portfolio)
            self.assertEqual(recovered_statement, before_statement)
            self.assertEqual(transport.reconnect_urls, [second.websocket.url])

            # No proposal, transaction subscription, buy, sell or mutation call.
            forbidden = {
                "proposal", "buy", "sell", "cancel", "transaction",
                "proposal_open_contract", "contract_update",
            }
            self.assertFalse(forbidden.intersection(transport.actions))
            self.assertEqual(
                set(transport.actions),
                {"balance", "portfolio", "statement"},
            )

            await adapter.close()

        self.assertEqual(manager.calls, 2)
        self.assertTrue(transport.closed)
        self.assertIsNone(adapter.transport)
        self.assertIsNone(adapter.account)

    async def test_transport_ping_waits_for_matching_pong(self):
        websocket = FakeWebSocket()

        async def fake_connect(_url, **kwargs):
            fake_connect.kwargs = kwargs
            return websocket

        fake_connect.kwargs = {}
        transport = DerivWebSocketTransport(
            "wss://api.derivws.com/trading/v1/options/ws/real?otp=MOCK",
            timeout_seconds=1.0,
        )
        with patch("runtime.adapters.deriv_ws.connect", side_effect=fake_connect):
            await transport.connect()
            latency = await transport.ping()
            await transport.close()

        self.assertEqual(websocket.ping_count, 1)
        self.assertTrue(websocket.closed)
        self.assertGreaterEqual(latency, 0.0)
        self.assertEqual(fake_connect.kwargs["ping_interval"], 20.0)
        self.assertEqual(fake_connect.kwargs["ping_timeout"], 20.0)


if __name__ == "__main__":
    unittest.main()
