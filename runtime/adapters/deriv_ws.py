from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

from websockets.asyncio.client import ClientConnection, connect


class DerivTransportError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code or str(message)
        self.details = dict(details or {})


@dataclass
class Subscription:
    key: str
    payload: dict[str, Any]
    queue: asyncio.Queue[dict[str, Any]]
    request_id: int | None = None
    subscription_id: str | None = None


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
    ):
        if not url:
            raise DerivTransportError("DERIV_WS_URL_MISSING")
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.ping_interval = ping_interval
        self.ws: ClientConnection | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._subscriptions: dict[str, Subscription] = {}
        self._subscription_by_request_id: dict[int, str] = {}
        self._subscription_by_id: dict[str, str] = {}
        self.last_reader_error: dict[str, Any] | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self.ws is not None:
            return
        self.ws = await connect(
            self.url,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_interval,
            close_timeout=5,
            max_size=2_000_000,
        )
        self._reader_task = asyncio.create_task(self._reader_loop())

    @staticmethod
    def _reader_error_details(exc: Exception) -> dict[str, Any]:
        if isinstance(exc, DerivTransportError):
            details = {"code": exc.code, "exception_type": type(exc).__name__}
            details.update(exc.details)
            return details
        details: dict[str, Any] = {
            "code": "TRANSPORT_READER_FAILED",
            "exception_type": type(exc).__name__,
        }
        close_code = getattr(exc, "code", None)
        if close_code is not None:
            details["websocket_close_code"] = close_code
        if isinstance(exc, json.JSONDecodeError):
            details["json_line"] = exc.lineno
            details["json_column"] = exc.colno
        return details

    async def _reader_loop(self) -> None:
        ws = self.ws
        if ws is None:
            return
        try:
            while True:
                raw = await ws.recv()
                message = json.loads(raw)
                if not isinstance(message, dict):
                    raise DerivTransportError(
                        "WEBSOCKET_MESSAGE_NOT_OBJECT",
                        code="WEBSOCKET_MESSAGE_NOT_OBJECT",
                    )

                request_id = message.get("req_id")
                if isinstance(request_id, int) and request_id in self._pending:
                    future = self._pending[request_id]
                    if not future.done():
                        if "error" in message:
                            broker_error = message["error"]
                            if isinstance(broker_error, dict):
                                code = str(broker_error.get("code") or "BROKER_REQUEST_FAILED")
                                future.set_exception(
                                    DerivTransportError(code, code=code, details=broker_error)
                                )
                            else:
                                future.set_exception(DerivTransportError(str(broker_error)))
                        else:
                            future.set_result(message)
                    continue

                key = (
                    self._subscription_by_request_id.get(request_id)
                    if isinstance(request_id, int)
                    else None
                )
                if key is not None:
                    subscription = self._subscriptions.get(key)
                    if subscription is not None:
                        subscription_meta = message.get("subscription")
                        subscription_id = (
                            subscription_meta.get("id")
                            if isinstance(subscription_meta, dict)
                            else None
                        )
                        if subscription_id is not None:
                            subscription.subscription_id = str(subscription_id)
                            self._subscription_by_id[str(subscription_id)] = key
                        subscription.queue.put_nowait(message)
                    continue

                subscription_meta = message.get("subscription")
                subscription_id = (
                    subscription_meta.get("id")
                    if isinstance(subscription_meta, dict)
                    else None
                )
                if subscription_id is not None:
                    key = self._subscription_by_id.get(str(subscription_id))
                    subscription = self._subscriptions.get(key) if key is not None else None
                    if subscription is not None:
                        subscription.queue.put_nowait(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            details = self._reader_error_details(exc)
            self.last_reader_error = details
            transport_error = DerivTransportError(
                "TRANSPORT_READER_FAILED",
                code="TRANSPORT_READER_FAILED",
                details=details,
            )
            self._fail_pending(transport_error)
            for subscription in list(self._subscriptions.values()):
                subscription.queue.put_nowait({"error": details})
        finally:
            if self.ws is ws:
                self.ws = None
            try:
                await ws.close()
            except Exception:
                pass

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
                    broker_error = message["error"]
                    if isinstance(broker_error, dict):
                        code = str(broker_error.get("code") or "BROKER_SUBSCRIPTION_FAILED")
                        raise DerivTransportError(code, code=code, details=broker_error)
                    raise DerivTransportError(str(broker_error))
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
            if subscription.subscription_id is not None:
                self._subscription_by_id.pop(subscription.subscription_id, None)
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
        reader = self._reader_task
        self._reader_task = None
        if reader is not None:
            reader.cancel()
            try:
                await reader
            except asyncio.CancelledError:
                pass

        if self.ws is not None:
            await self.ws.close()
        self.ws = None
        self._fail_pending(DerivTransportError("BROKER_SESSION_CLOSED"))

        self._subscription_by_request_id.clear()
        self._subscription_by_id.clear()
