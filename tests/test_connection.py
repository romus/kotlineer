from __future__ import annotations

import asyncio
import json

import pytest

from kotlineer.connection import LspConnection
from kotlineer.types import LspError, RequestTimeoutError


def _encode_lsp_message(obj: dict) -> bytes:
    body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def _make_response(req_id: int, result: object = None) -> bytes:
    return _encode_lsp_message({"jsonrpc": "2.0", "id": req_id, "result": result})


def _make_error_response(req_id: int, code: int, message: str) -> bytes:
    return _encode_lsp_message(
        {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
    )


def _make_notification(method: str, params: dict | None = None) -> bytes:
    msg: dict = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    return _encode_lsp_message(msg)


def _make_server_request(req_id: int, method: str) -> bytes:
    return _encode_lsp_message({"jsonrpc": "2.0", "id": req_id, "method": method})


class FakeWriter:
    def __init__(self):
        self.written = bytearray()

    def write(self, data: bytes) -> None:
        self.written.extend(data)

    def get_messages(self) -> list[dict]:
        raw = bytes(self.written)
        messages = []
        while raw:
            idx = raw.find(b"\r\n\r\n")
            if idx < 0:
                break
            header_part = raw[:idx].decode("ascii")
            length = int(header_part.split(":")[1].strip())
            body_start = idx + 4
            body = raw[body_start : body_start + length]
            messages.append(json.loads(body))
            raw = raw[body_start + length :]
        return messages


async def _make_connection(
    response_data: bytes = b"",
    request_timeout: float = 5.0,
) -> tuple[LspConnection, FakeWriter]:
    reader = asyncio.StreamReader()
    reader.feed_data(response_data)
    reader.feed_eof()
    writer = FakeWriter()
    conn = LspConnection(reader, writer, request_timeout=request_timeout)  # type: ignore[arg-type]
    return conn, writer


class TestWriteMessage:
    async def test_sends_valid_jsonrpc(self):
        conn, writer = await _make_connection()
        conn._write_message({"jsonrpc": "2.0", "method": "test"})
        msgs = writer.get_messages()
        assert len(msgs) == 1
        assert msgs[0] == {"jsonrpc": "2.0", "method": "test"}


class TestSendNotification:
    async def test_sends_notification_without_params(self):
        conn, writer = await _make_connection()
        await conn.send_notification("initialized")
        msgs = writer.get_messages()
        assert len(msgs) == 1
        assert msgs[0]["method"] == "initialized"
        assert "id" not in msgs[0]
        assert "params" not in msgs[0]

    async def test_sends_notification_with_params(self):
        conn, writer = await _make_connection()
        await conn.send_notification("textDocument/didOpen", {"textDocument": {"uri": "f"}})
        msgs = writer.get_messages()
        assert msgs[0]["params"] == {"textDocument": {"uri": "f"}}


class TestSendRequest:
    async def test_request_gets_response(self):
        response = _make_response(1, {"capabilities": {}})
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        conn = LspConnection(reader, writer, request_timeout=5.0)  # type: ignore[arg-type]
        await conn.start()

        # Feed response after request is sent
        async def feed_later():
            await asyncio.sleep(0.01)
            reader.feed_data(response)
            reader.feed_eof()

        asyncio.create_task(feed_later())
        result = await conn.send_request("initialize", {"processId": None})
        assert result == {"capabilities": {}}
        await conn.close()

    async def test_request_increments_id(self):
        conn, writer = await _make_connection()
        # Don't await responses — just check IDs are incrementing
        assert conn._next_id == 1
        # Manually create futures to avoid timeout
        conn._next_id = 1
        conn._write_message({"jsonrpc": "2.0", "id": 1, "method": "a"})
        conn._next_id = 2
        conn._write_message({"jsonrpc": "2.0", "id": 2, "method": "b"})
        msgs = writer.get_messages()
        assert msgs[0]["id"] == 1
        assert msgs[1]["id"] == 2

    async def test_request_timeout_raises(self):
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        conn = LspConnection(reader, writer, request_timeout=0.05)  # type: ignore[arg-type]
        await conn.start()

        with pytest.raises(RequestTimeoutError) as exc_info:
            await conn.send_request("textDocument/hover")

        assert exc_info.value.method == "textDocument/hover"
        assert exc_info.value.timeout == 0.05
        reader.feed_eof()
        await conn.close()

    async def test_error_response_raises_lsp_error(self):
        error_resp = _make_error_response(1, -32600, "Invalid Request")
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        conn = LspConnection(reader, writer, request_timeout=5.0)  # type: ignore[arg-type]
        await conn.start()

        async def feed_later():
            await asyncio.sleep(0.01)
            reader.feed_data(error_resp)
            reader.feed_eof()

        asyncio.create_task(feed_later())

        with pytest.raises(LspError) as exc_info:
            await conn.send_request("test")

        assert exc_info.value.code == -32600
        assert "Invalid Request" in str(exc_info.value)
        await conn.close()


class TestNotificationHandlers:
    async def test_dispatches_to_handler(self):
        notification = _make_notification(
            "textDocument/publishDiagnostics", {"uri": "f", "diagnostics": []}
        )
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        conn = LspConnection(reader, writer, request_timeout=5.0)  # type: ignore[arg-type]

        received = []
        conn.on_notification(
            "textDocument/publishDiagnostics", lambda params: received.append(params)
        )

        await conn.start()
        reader.feed_data(notification)
        reader.feed_eof()

        # Give listener time to process
        await asyncio.sleep(0.05)
        await conn.close()

        assert len(received) == 1
        assert received[0]["uri"] == "f"

    async def test_multiple_handlers(self):
        notification = _make_notification("test/event", {"data": 1})
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        conn = LspConnection(reader, writer, request_timeout=5.0)  # type: ignore[arg-type]

        calls = []
        conn.on_notification("test/event", lambda p: calls.append("a"))
        conn.on_notification("test/event", lambda p: calls.append("b"))

        await conn.start()
        reader.feed_data(notification)
        reader.feed_eof()
        await asyncio.sleep(0.05)
        await conn.close()

        assert calls == ["a", "b"]

    async def test_unregistered_notification_ignored(self):
        notification = _make_notification("unknown/method", {})
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        conn = LspConnection(reader, writer, request_timeout=5.0)  # type: ignore[arg-type]

        await conn.start()
        reader.feed_data(notification)
        reader.feed_eof()
        await asyncio.sleep(0.05)
        await conn.close()
        # No error — just silently ignored


class TestServerRequest:
    async def test_workspace_configuration_responds_with_empty_configs(self):
        server_req = _make_server_request(99, "workspace/configuration")
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        conn = LspConnection(reader, writer, request_timeout=5.0)  # type: ignore[arg-type]

        await conn.start()
        reader.feed_data(server_req)
        reader.feed_eof()
        await asyncio.sleep(0.05)
        await conn.close()

        msgs = writer.get_messages()
        assert len(msgs) == 1
        assert msgs[0]["id"] == 99
        assert msgs[0]["result"] == [{}]

    async def test_unknown_request_responds_null(self):
        server_req = _make_server_request(100, "window/showMessage")
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        conn = LspConnection(reader, writer, request_timeout=5.0)  # type: ignore[arg-type]

        await conn.start()
        reader.feed_data(server_req)
        reader.feed_eof()
        await asyncio.sleep(0.05)
        await conn.close()

        msgs = writer.get_messages()
        assert len(msgs) == 1
        assert msgs[0]["id"] == 100
        assert msgs[0]["result"] is None


class TestClose:
    async def test_cancels_pending_requests(self):
        reader = asyncio.StreamReader()
        writer = FakeWriter()
        conn = LspConnection(reader, writer, request_timeout=5.0)  # type: ignore[arg-type]
        await conn.start()

        future = asyncio.get_event_loop().create_future()
        conn._pending[1] = future

        await conn.close()
        assert len(conn._pending) == 0

    async def test_close_idempotent(self):
        conn, _ = await _make_connection()
        await conn.close()
        await conn.close()  # Should not raise


class TestReadMessage:
    async def test_reads_valid_message(self):
        data = _encode_lsp_message({"jsonrpc": "2.0", "method": "test"})
        reader = asyncio.StreamReader()
        reader.feed_data(data)
        reader.feed_eof()
        writer = FakeWriter()
        conn = LspConnection(reader, writer, request_timeout=5.0)  # type: ignore[arg-type]

        msg = await conn._read_message()
        assert msg == {"jsonrpc": "2.0", "method": "test"}

    async def test_returns_none_on_eof(self):
        reader = asyncio.StreamReader()
        reader.feed_eof()
        writer = FakeWriter()
        conn = LspConnection(reader, writer, request_timeout=5.0)  # type: ignore[arg-type]

        msg = await conn._read_message()
        assert msg is None
