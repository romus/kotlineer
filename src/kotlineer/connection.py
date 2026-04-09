from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from .types import LspError, RequestTimeoutError

logger = logging.getLogger(__name__)


class LspConnection:
    """JSON-RPC connection over stdio streams using LSP Content-Length framing."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter | asyncio.subprocess.Process,
        *,
        request_timeout: float = 30.0,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._request_timeout = request_timeout

        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._notification_handlers: dict[str, list[Callable[..., Any]]] = {}
        self._listen_task: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        """Start the background listener for incoming messages."""
        self._listen_task = asyncio.create_task(self._listen())

    async def close(self) -> None:
        """Stop listening and cancel pending requests."""
        self._closed = True
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        # Cancel all pending requests
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

    async def send_request(self, method: str, params: Any = None) -> Any:
        """Send a JSON-RPC request and wait for the response."""
        request_id = self._next_id
        self._next_id += 1

        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params

        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        self._write_message(message)
        logger.debug("→ request #%d: %s", request_id, method)

        try:
            result = await asyncio.wait_for(future, timeout=self._request_timeout)
            return result
        except TimeoutError:
            self._pending.pop(request_id, None)
            raise RequestTimeoutError(method, self._request_timeout)

    async def send_notification(self, method: str, params: Any = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            message["params"] = params

        self._write_message(message)
        logger.debug("→ notification: %s", method)

    def on_notification(self, method: str, handler: Callable[..., Any]) -> None:
        """Register a handler for server-initiated notifications."""
        self._notification_handlers.setdefault(method, []).append(handler)

    def _write_message(self, message: dict[str, Any]) -> None:
        """Serialize and write a JSON-RPC message with Content-Length header."""
        body = json.dumps(message, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")

        # _writer can be either StreamWriter or subprocess stdin
        writer = self._writer
        if hasattr(writer, "write"):
            writer.write(header + body)  # type: ignore[union-attr]
        else:
            raise RuntimeError("Writer is not writable")

    async def _listen(self) -> None:
        """Background loop: read and dispatch incoming JSON-RPC messages."""
        try:
            while not self._closed:
                message = await self._read_message()
                if message is None:
                    break
                self._dispatch(message)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error in LSP listen loop")
            # Fail all pending requests
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(LspError("Connection lost"))
            self._pending.clear()

    async def _read_message(self) -> dict[str, Any] | None:
        """Read one JSON-RPC message using Content-Length framing."""
        content_length = -1

        # Read headers
        while True:
            line = await self._reader.readline()
            if not line:
                return None  # EOF

            line_str = line.decode("ascii").strip()
            if not line_str:
                break  # Empty line = end of headers

            if line_str.lower().startswith("content-length:"):
                content_length = int(line_str.split(":", 1)[1].strip())

        if content_length < 0:
            return None

        # Read body
        body = await self._reader.readexactly(content_length)
        data = json.loads(body)
        return data

    def _dispatch(self, message: dict[str, Any]) -> None:
        """Route an incoming message to the right handler."""
        if "id" in message and "method" not in message:
            # Response to a request we sent
            req_id = message["id"]
            future = self._pending.pop(req_id, None)
            if future is None or future.done():
                return

            if "error" in message:
                err = message["error"]
                future.set_exception(
                    LspError(
                        err.get("message", "Unknown error"),
                        code=err.get("code", -1),
                        data=err.get("data"),
                    )
                )
            else:
                future.set_result(message.get("result"))

        elif "method" in message and "id" not in message:
            # Server notification
            method = message["method"]
            params = message.get("params")
            logger.debug("← notification: %s", method)
            for handler in self._notification_handlers.get(method, []):
                try:
                    handler(params)
                except Exception:
                    logger.exception("Error in notification handler for %s", method)

        elif "method" in message and "id" in message:
            # Server request (e.g. window/showMessage, workspace/configuration)
            req_id = message["id"]
            method = message["method"]

            if method == "workspace/configuration":
                # Return an empty config object per requested item
                items = (message.get("params") or {}).get("items", [{}])
                result = [{} for _ in items]
            else:
                result = None

            response = {"jsonrpc": "2.0", "id": req_id, "result": result}
            self._write_message(response)
            logger.debug("← server request: %s (auto-responded)", method)
