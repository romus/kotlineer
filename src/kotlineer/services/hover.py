from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..connection import LspConnection


class HoverService:
    """Hover information and signature help."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection

    async def hover(self, uri: str, line: int, character: int) -> dict[str, Any] | None:
        """Get hover info (type, documentation) at a position."""
        return await self._connection.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )

    async def signature_help(self, uri: str, line: int, character: int) -> dict[str, Any] | None:
        """Get signature help (parameter hints) at a position."""
        return await self._connection.send_request(
            "textDocument/signatureHelp",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )
