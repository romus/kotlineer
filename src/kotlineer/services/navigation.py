from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..connection import LspConnection


class NavigationService:
    """Go-to-definition, find references, type definition, implementation."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection

    async def definition(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        """Go to definition."""
        return await self._connection.send_request(
            "textDocument/definition",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )

    async def type_definition(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        """Go to type definition."""
        return await self._connection.send_request(
            "textDocument/typeDefinition",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )

    async def declaration(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | dict[str, Any] | None:
        """Go to declaration."""
        return await self._connection.send_request(
            "textDocument/declaration",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )

    async def implementation(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | None:
        """Find implementations."""
        return await self._connection.send_request(
            "textDocument/implementation",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )

    async def references(
        self,
        uri: str,
        line: int,
        character: int,
        include_declaration: bool = True,
    ) -> list[dict[str, Any]] | None:
        """Find all references."""
        return await self._connection.send_request(
            "textDocument/references",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
                "context": {"includeDeclaration": include_declaration},
            },
        )
