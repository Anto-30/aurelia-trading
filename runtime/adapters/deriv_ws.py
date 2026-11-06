from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, AsyncIterator

from websockets.asyncio.client import ClientConnection, connect


_SAFE_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


def _safe_code(value: Any, fallback: str) -> str:
    candidate = str(value or "").strip()
    return candidate if _SAFE_CODE.fullmatch(candidate) else fallback


class DerivTransportError(RuntimeError):
    """Transport failure with sanitized, structured diagnostics."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        failure_type: str | None = None,
        close_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = _safe_code(code or message, "TRANSPORT_ERROR")
        self.details = dict(details or {})
        self.failure_type = failure_type
        self.close_code = close_code


@dataclass
class Subscription:
    key: str
    payload: dict[str, Any]
    queue: asyncio.Queue[dict[str, Any]]
    request_id: int | None = None
    subscription_id: str | None = None


class DerivWebSocketTransport:
    """Single-reader WebSocket transport with app heartbeat and safe routing.

    Exactly one background task calls recv(). Request replies are correlated by
    req_id. Subscription updates are routed by the broker-issued subscription.id
    after the first response. Account credentials are never constructed here.
    """

    def __init__(
        self,
        url: str,
        *,
        timeout_seconds: float = 10.0,
        ping_interval: float = 20.0,
        application_ping_interval: float = 45.0,
    ) -> None:
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
        self._subscription_by_id: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self.last_transport_failure: dict[str, Any] | None = None
        self.last_reader_error: dict[str, Any] | None = None

    async def connect(self) -> None:
        if self.ws is not None:
            return
        self.last_transport_failure = None
        self.last_reader_error = None
        self.ws = await connect(
            self.url,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_interval,
            close_timeout=5,
            max_size=2_000_000,
        )
        self._reader_task = asyncio.create_task(self._reader_loop())
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    @staticmethod
    def _reader_error_details(exc: Exception) -> dict[str, Any]:
        if isinstance(exc, DerivTransportError):
            details = {
                "code": exc.code,
                "exception_type": type(exc).__name__,
            }
            if exc.failure_type:
                details["failure_type"] = _safe_code(exc.failure_type.upper(), "UNKNOWN")
            if isinstance(exc.close_code, int) and not isinstance(exc.close_code, bool):
                details["websocket_close_code"] = exc.close_code
            return details
        close_code = getattr(exc, "code", None)
        if isinstance(close_code, bool) or not isinstance(close_code, int):
            close_code = None
        details: dict[str, Any] = {
            "code": "TRANSPORT_READER_FAILED",
            "exception_type": type(exc).__name__,
        }
        if close_code is not None:
            details["websocket_close_code"] = close_code
        if isinstance(exc, json.JSONDecodeError):
            details["json_line"] = exc.lineno
            details["json_column"] = exc.colno
        return details

    def _broadcast_transport_failure(self, code: str, exc: Exception) -> None:
        safe_code = _safe_code(code, "TRANSPORT_FAILURE")
        failure_type = type(exc).__name__
        close_code = getattr(exc, "code", None)
        if isinstance(close_code, bool) or not isinstance(close_code, int):
            close_code = None
        metadata: dict[str, Any] = {
            "code": safe_code,
            "failure_type": failure_type,
        }
        if close_code is not None:
            metadata["close_code"] = close_code
        if self.last_transport_failure is None:
            self.last_transport_failure = metadata.copy()
        if self.last_reader_error is None and safe_code == "TRANSPORT_READER_FAILED":
            self.last_reader_error = {
                "code": safe_code,
                "exception_type": failure_type,
                **({"websocket_close_code": close_code} if close_code is not None else {}),
            }
        safe_error = DerivTransportError(
            safe_code,
            code=safe_code,
            failure_type=failure_type,
            close_code=close_code,
            details=metadata,
        )
        self._fail_pending(safe_error)
        for subscription in list(self._subscriptions.values()):
            subscription.queue.put_nowait({"error": metadata.copy()})

    async def _reader_loop(self) -> None:
        websocket = self.ws
        if websocket is None:
            return
        try:
            while True:
                raw = await websocket.recv()
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
                            broker_error = message.get("error")
                            raw_code = (
                                broker_error.get("code")
                                if isinstance(broker_error, dict)
                                else None
                            )
                            safe_code = _safe_code(raw_code, "BROKER_REQUEST_FAILED")
                            future.set_exception(
                                DerivTransportError(
                                    safe_code,
                                    code=safe_code,
                                    details={"code": safe_code},
                                )
                            )
                        else:
                            future.set_result(message)
                    continue

                key = (
                    self._subscription_by_request_id.get(request_id)
                    if isinstance(request_id, int)
                    else None
                )
                subscription = self._subscriptions.get(key) if key else None
                subscription_meta = message.get("subscription")
                subscription_id = (
                    subscription_meta.get("id")
                    if isinstance(subscription_meta, dict)
                    else None
                )
                if subscription is not None:
                    if subscription_id is not None:
                        subscription.subscription_id = str(subscription_id)
                        self._subscription_by_id[str(subscription_id)] = subscription.key
                    subscription.queue.put_nowait(message)
                    continue

                if subscription_id is not None:
                    routed_key = self._subscription_by_id.get(str(subscription_id))
                    routed = self._subscriptions.get(routed_key) if routed_key else None
                    if routed is not None:
                        routed.queue.put_nowait(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            details = self._reader_error_details(exc)
            safe_code = _safe_code(details.get("code"), "TRANSPORT_READER_FAILED")
            failure = DerivTransportError(
                safe_code,
                code=safe_code,
                details=details,
                failure_type=type(exc).__name__,
                close_code=details.get("websocket_close_code"),
            )
            self.last_reader_error = details
            if self.last_transport_failure is None:
                self.last_transport_failure = details.copy()
            self._fail_pending(failure)
            for subscription in list(self._subscriptions.values()):
                subscription.queue.put_nowait({"error": details.copy()})
            keepalive = self._keepalive_task
            if keepalive is not None and keepalive is not asyncio.current_task():
                keepalive.cancel()
        finally:
            if self.ws is websocket:
                self.ws = None
            try:
                await websocket.close()
            except Exception:
                pass

    async def _keepalive_loop(self) -> None:
        """Send Deriv's documented JSON ping at the documented 30–60s cadence."""
        try:
            while True:
                await asyncio.sleep(self.application_ping_interval)
                if self.ws is None:
                    return
                response = await self.request({"ping": 1})
                if response.get("msg_type") != "ping" or response.get("ping") != "pong":
                    raise DerivTransportError(
                        "DERIV_PING_RESPONSE_INVALID",
                        code="DERIV_PING_RESPONSE_INVALID",
                    )
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
        if isinstance(request_id, bool) or not isinstance(request_id, int) or request_id <= 0:
            raise ValueError("REQUEST_ID_MUST_BE_POSITIVE_INTEGER")
        self._request_id = max(self._request_id, request_id)

    async def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.ws is None:
            raise DerivTransportError("BROKER_SESSION_NOT_CONNECTED")
        supplied_id = payload.get("req_id")
        if supplied_id is not None:
            if isinstance(supplied_id, bool) or not isinstance(supplied_id, int) or supplied_id <= 0:
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
            raise DerivTransportError("BROKER_REQUEST_TIMEOUT", code="BROKER_REQUEST_TIMEOUT") from exc
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
            raise DerivTransportError("DUPLICATE_SUBSCRIPTION")
        subscription = Subscription(
            key=key,
            payload={**payload, "subscribe": 1},
            queue=asyncio.Queue(),
        )
        subscription.request_id = self._next_request_id()
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
                    raw_code = error.get("code") if isinstance(error, dict) else None
                    safe_code = _safe_code(raw_code, "BROKER_SUBSCRIPTION_FAILED")
                    failure_type = error.get("failure_type") if isinstance(error, dict) else None
                    close_code = error.get("close_code") if isinstance(error, dict) else None
                    raise DerivTransportError(
                        safe_code,
                        code=safe_code,
                        details={"code": safe_code},
                        failure_type=_safe_code(failure_type.upper(), "UNKNOWN") if isinstance(failure_type, str) else None,
                        close_code=close_code if isinstance(close_code, int) and not isinstance(close_code, bool) else None,
                    )
                yield message
        finally:
            # The forget endpoint needs the broker-issued subscription ID,
            # never the local request ID used to create the stream.
            if self.ws is not None and subscription.subscription_id is not None:
                try:
                    await self.ws.send(json.dumps({
                        "forget": subscription.subscription_id,
                        "req_id": self._next_request_id(),
                    }))
                except Exception:
                    pass
            if subscription.request_id is not None:
                self._subscription_by_request_id.pop(subscription.request_id, None)
            if subscription.subscription_id is not None:
                self._subscription_by_id.pop(subscription.subscription_id, None)
            self._subscriptions.pop(key, None)

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def reconnect(self, fresh_url: str | None = None) -> None:
        """Reconnect with a new URL when supplied, retaining active stream objects."""
        active = [
            (key, sub, dict(sub.payload))
            for key, sub in self._subscriptions.items()
        ]
        await self._close(preserve_subscriptions=True)
        if fresh_url:
            self.url = fresh_url
        await self.connect()
        for key, sub, payload in active:
            sub.request_id = self._next_request_id()
            sub.subscription_id = None
            self._subscription_by_request_id[sub.request_id] = key
            await self.ws.send(json.dumps({**payload, "req_id": sub.request_id}))

    async def _close(self, *, preserve_subscriptions: bool) -> None:
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
            try:
                await websocket.close()
            except Exception:
                pass
        self.ws = None
        self._fail_pending(DerivTransportError("BROKER_SESSION_CLOSED"))
        self._subscription_by_request_id.clear()
        self._subscription_by_id.clear()
        if not preserve_subscriptions:
            for subscription in list(self._subscriptions.values()):
                subscription.queue.put_nowait({"error": {"code": "BROKER_SESSION_CLOSED"}})
            self._subscriptions.clear()

    async def close(self) -> None:
        await self._close(preserve_subscriptions=False)
