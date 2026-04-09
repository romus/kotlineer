from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..connection import LspConnection


class HierarchyService:
    """Call hierarchy and type hierarchy."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection

    # ── Call Hierarchy ──────────────────────────────────────────────

    async def prepare_call_hierarchy(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | None:
        """Prepare call hierarchy items at a position."""
        return await self._connection.send_request(
            "textDocument/prepareCallHierarchy",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )

    async def incoming_calls(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | None:
        """Find functions that call the function at the given position."""
        items = await self.prepare_call_hierarchy(uri, line, character)
        if not items:
            return None
        return await self._connection.send_request(
            "callHierarchy/incomingCalls",
            {"item": items[0]},
        )

    async def outgoing_calls(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | None:
        """Find functions called by the function at the given position."""
        items = await self.prepare_call_hierarchy(uri, line, character)
        if not items:
            return None
        return await self._connection.send_request(
            "callHierarchy/outgoingCalls",
            {"item": items[0]},
        )

    # ── Type Hierarchy ──────────────────────────────────────────────

    async def prepare_type_hierarchy(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | None:
        """Prepare type hierarchy items at a position."""
        return await self._connection.send_request(
            "textDocument/prepareTypeHierarchy",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )

    async def supertypes(self, uri: str, line: int, character: int) -> list[dict[str, Any]] | None:
        """Find supertypes of the type at the given position."""
        items = await self.prepare_type_hierarchy(uri, line, character)
        if not items:
            return None
        return await self._connection.send_request(
            "typeHierarchy/supertypes",
            {"item": items[0]},
        )

    async def subtypes(self, uri: str, line: int, character: int) -> list[dict[str, Any]] | None:
        """Find subtypes of the type at the given position."""
        items = await self.prepare_type_hierarchy(uri, line, character)
        if not items:
            return None
        return await self._connection.send_request(
            "typeHierarchy/subtypes",
            {"item": items[0]},
        )
