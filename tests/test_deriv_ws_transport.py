from __future__ import annotations

import asyncio

import pytest

from runtime.adapters.deriv_ws import (
    DerivTransportReaderError,
    DerivWebSocketTransport,
    Subscription,
)


class ReaderFailureSocket:
    def __init__(self):
        self.closed = False

    async def recv(self):
        raise ConnectionResetError("DO_NOT_LOG_RAW_SOCKET_MESSAGE")

    async def send(self, payload):
        return None

    async def close(self):
        self.closed = True


class SendOnlySocket:
    async def send(self, payload):
        return None


@pytest.mark.asyncio
async def test_reader_failure_is_structured_and_redacts_raw_exception_message():
    transport = DerivWebSocketTransport("wss://example.invalid")
    socket = ReaderFailureSocket()
    transport.ws = socket
    subscription = Subscription(
        key="ticks:R_100",
        payload={"ticks": "R_100"},
        queue=asyncio.Queue(),
        request_id=1,
    )
    transport._subscriptions[subscription.key] = subscription
    pending = asyncio.get_running_loop().create_future()
    transport._pending[2] = pending

    await transport._reader_loop()

    queued = await subscription.queue.get()
    assert queued["error"]["code"] == "TRANSPORT_READER_FAILED"
    assert queued["error"]["error_class"] == "ConnectionResetError"
    assert "DO_NOT_LOG_RAW_SOCKET_MESSAGE" not in str(queued)
    assert socket.closed
    assert transport.ws is None
    with pytest.raises(DerivTransportReaderError) as error:
        await pending
    assert error.value.error_class == "ConnectionResetError"
    assert error.value.retryable is True


@pytest.mark.asyncio
async def test_subscribe_maps_reader_failure_to_typed_retryable_error():
    transport = DerivWebSocketTransport("wss://example.invalid")
    transport.ws = SendOnlySocket()
    iterator = transport.subscribe("ticks:R_100", {"ticks": "R_100"}).__aiter__()
    task = asyncio.create_task(iterator.__anext__())
    await asyncio.sleep(0)

    subscription = transport._subscriptions["ticks:R_100"]
    subscription.queue.put_nowait({
        "error": {
            "code": "TRANSPORT_READER_FAILED",
            "error_class": "ConnectionClosedOK",
            "close_code": 1000,
        }
    })
    with pytest.raises(DerivTransportReaderError) as error:
        await task
    assert error.value.error_class == "ConnectionClosedOK"
    assert error.value.close_code == 1000
    assert error.value.retryable is True


@pytest.mark.asyncio
async def test_protocol_decode_failure_is_not_marked_retryable():
    transport = DerivWebSocketTransport("wss://example.invalid")

    class InvalidJsonSocket(ReaderFailureSocket):
        async def recv(self):
            return "{not-json"

    socket = InvalidJsonSocket()
    transport.ws = socket
    subscription = Subscription(
        key="ticks:R_100",
        payload={"ticks": "R_100"},
        queue=asyncio.Queue(),
        request_id=1,
    )
    transport._subscriptions[subscription.key] = subscription

    await transport._reader_loop()
    queued = await subscription.queue.get()
    assert queued["error"]["error_class"] == "JSONDecodeError"
    assert "TRANSPORT_READER_FAILED" in str(queued["error"])
    assert socket.closed
