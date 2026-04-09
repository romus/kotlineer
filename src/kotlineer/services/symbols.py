from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import LspConnection


class SymbolService:
    """Document symbols and workspace symbol search."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection

    async def document_symbols(self, uri: str) -> list[dict[str, Any]] | None:
        """Get all symbols in a document (classes, functions, etc.)."""
        return await self._connection.send_request(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": uri}},
        )

    async def workspace_symbols(self, query: str) -> list[dict[str, Any]] | None:
        """Search for symbols across the entire workspace."""
        return await self._connection.send_request(
            "workspace/symbol",
            {"query": query},
        )
