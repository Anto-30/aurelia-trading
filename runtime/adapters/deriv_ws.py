from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

from websockets.asyncio.client import ClientConnection, connect


class DerivTransportError(RuntimeError):
    """Transport failure with safe, structured diagnostics."""

    def __init__(
        self,
        message: str,
        *,
        failure_type: str | None = None,
        close_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_type = failure_type
        self.close_code = close_code


@dataclass
class Subscription:
    key: str
    payload: dict[str, Any]
    queue: asyncio.Queue[dict[str, Any]]
    request_id: int | None = None


class DerivWebSocketTransport:
    """Single-reader WebSocket transport.

    Exactly one background task calls recv(). Requests are correlated through
    req_id and subscription messages are delivered through dedicated queues.
    This prevents concurrent recv() calls from racing requests and tick streams.
    """

    def __init__(
        self,
        url: str,
        *,
        timeout_seconds: float = 10.0,
        ping_interval: float = 20.0,
        application_ping_interval: float = 45.0,
    ):
        if not url:
            raise DerivTransportError("DERIV_WS_URL_MISSING")
        if (
            isinstance(application_ping_interval, bool)
            or not isinstance(application_ping_interval, (int, float))
            or application_ping_interval <= 0
        ):
            raise DerivTransportError("APPLICATION_PING_INTERVAL_INVALID")
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.ping_interval = ping_interval
        self.application_ping_interval = float(application_ping_interval)
        self.ws: ClientConnection | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._keepalive_task: asyncio.Task[None] | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._subscriptions: dict[str, Subscription] = {}
        self._subscription_by_request_id: dict[int, str] = {}
        self._lock = asyncio.Lock()
        self.last_transport_failure: dict[str, Any] | None = None

    async def connect(self) -> None:
        if self.ws is not None:
            return
        self.last_transport_failure = None
        self.ws = await connect(
            self.url,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_interval,
            close_timeout=5,
            max_size=2_000_000,
        )
        self._reader_task = asyncio.create_task(self._reader_loop())
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def _reader_loop(self) -> None:
        websocket = self.ws
        assert websocket is not None
        try:
            while True:
                raw = await websocket.recv()
                message = json.loads(raw)
                request_id = message.get("req_id")
                if isinstance(request_id, int) and request_id in self._pending:
                    future = self._pending[request_id]
                    if not future.done():
                        if "error" in message:
                            future.set_exception(
                                DerivTransportError(str(message["error"]))
                            )
                        else:
                            future.set_result(message)
                    continue

                if isinstance(request_id, int):
                    key = self._subscription_by_request_id.get(request_id)
                    if key is not None:
                        subscription = self._subscriptions.get(key)
                        if subscription is not None:
                            subscription.queue.put_nowait(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._broadcast_transport_failure("TRANSPORT_READER_FAILED", exc)
            keepalive = self._keepalive_task
            if keepalive is not None and keepalive is not asyncio.current_task():
                keepalive.cancel()
        finally:
            if self.ws is websocket:
                self.ws = None

    async def _keepalive_loop(self) -> None:
        """Send Deriv's documented JSON ping at the 30–60 second cadence."""
        try:
            while True:
                await asyncio.sleep(self.application_ping_interval)
                if self.ws is None:
                    return
                await self.request({"ping": 1})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._broadcast_transport_failure("TRANSPORT_KEEPALIVE_FAILED", exc)
            websocket = self.ws
            if websocket is not None:
                try:
                    await websocket.close()
                except Exception:
                    pass

    def _broadcast_transport_failure(self, code: str, exc: Exception) -> None:
        """Preserve exception class and close code, never arbitrary exception text."""
        close_code = getattr(exc, "code", None)
        if isinstance(close_code, bool) or not isinstance(close_code, int):
            close_code = None
        failure_type = type(exc).__name__
        metadata = {
            "code": code,
            "failure_type": failure_type,
            "close_code": close_code,
        }
        if self.last_transport_failure is None:
            self.last_transport_failure = metadata
        safe_error = DerivTransportError(
            code,
            failure_type=failure_type,
            close_code=close_code,
        )
        self._fail_pending(safe_error)
        for subscription in self._subscriptions.values():
            subscription.queue.put_nowait({"error": metadata.copy()})

    def _fail_pending(self, exc: Exception) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)
        self._pending.clear()

    def allocate_request_id(self) -> int:
        """Allocate the next transport-wide request id synchronously."""
        return self._next_request_id()

    def reserve_request_id(self, request_id: int) -> None:
        """Advance the request-id high-water mark for external callers."""
        if not isinstance(request_id, int) or request_id <= 0:
            raise ValueError("REQUEST_ID_MUST_BE_POSITIVE_INTEGER")
        self._request_id = max(self._request_id, request_id)

    async def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.ws is None:
            raise DerivTransportError("BROKER_SESSION_NOT_CONNECTED")

        supplied_id = payload.get("req_id")
        if supplied_id is not None:
            if not isinstance(supplied_id, int) or supplied_id <= 0:
                raise DerivTransportError("REQUEST_ID_INVALID")
            self.reserve_request_id(supplied_id)
            request_id = supplied_id
        else:
            request_id = self._next_request_id()
        body = dict(payload)
        body["req_id"] = request_id

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = future
        try:
            await self.ws.send(json.dumps(body))
            return await asyncio.wait_for(future, timeout=self.timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise DerivTransportError("BROKER_REQUEST_TIMEOUT") from exc
        finally:
            self._pending.pop(request_id, None)

    async def subscribe(
        self,
        key: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        if self.ws is None:
            raise DerivTransportError("BROKER_SESSION_NOT_CONNECTED")
        if key in self._subscriptions:
            raise DerivTransportError(f"DUPLICATE_SUBSCRIPTION:{key}")

        subscription = Subscription(
            key=key,
            payload={**payload, "subscribe": 1},
            queue=asyncio.Queue(),
        )
        self._request_id += 1
        subscription.request_id = self._request_id
        self._subscriptions[key] = subscription
        self._subscription_by_request_id[subscription.request_id] = key

        try:
            await self.ws.send(
                json.dumps({**subscription.payload, "req_id": subscription.request_id})
            )
            while True:
                message = await subscription.queue.get()
                if "error" in message:
                    error = message["error"]
                    if isinstance(error, dict) and error.get("code") in {
                        "TRANSPORT_READER_FAILED",
                        "TRANSPORT_KEEPALIVE_FAILED",
                    }:
                        raise DerivTransportError(
                            str(error["code"]),
                            failure_type=error.get("failure_type"),
                            close_code=error.get("close_code"),
                        )
                    raise DerivTransportError(str(error))
                yield message
        finally:
            if self.ws is not None and subscription.request_id is not None:
                try:
                    await self.ws.send(
                        json.dumps(
                            {
                                "forget": [subscription.request_id],
                                "req_id": self._next_request_id(),
                            }
                        )
                    )
                except Exception:
                    pass
            self._subscription_by_request_id.pop(subscription.request_id, None)
            self._subscriptions.pop(key, None)

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def reconnect(self, fresh_url: str | None = None) -> None:
        '''Reconnect using a fresh authenticated URL when the caller supplies one.

        Reusing an expired/one-use OTP is intentionally not attempted.
        Existing subscriptions are re-established on the new transport with
        new request IDs.
        '''
        subscription_payloads = {
            key: subscription.payload.copy()
            for key, subscription in self._subscriptions.items()
        }
        await self.close()
        if fresh_url:
            self.url = fresh_url
        await self.connect()

        for key, payload in subscription_payloads.items():
            subscription = self._subscriptions.get(key)
            if subscription is None:
                continue
            self._request_id += 1
            subscription.request_id = self._request_id
            self._subscription_by_request_id[subscription.request_id] = key
            await self.ws.send(
                json.dumps({**payload, "req_id": subscription.request_id})
            )

    async def close(self) -> None:
        # Capture the socket before cancelling the reader: its finally block
        # clears self.ws, but the underlying socket still must be closed.
        websocket = self.ws

        keepalive = self._keepalive_task
        self._keepalive_task = None
        if keepalive is not None:
            keepalive.cancel()
            try:
                await keepalive
            except asyncio.CancelledError:
                pass

        reader = self._reader_task
        self._reader_task = None
        if reader is not None:
            reader.cancel()
            try:
                await reader
            except asyncio.CancelledError:
                pass

        if websocket is not None:
            await websocket.close()
        self.ws = None
        self._fail_pending(DerivTransportError("BROKER_SESSION_CLOSED"))

        self._subscription_by_request_id.clear()
