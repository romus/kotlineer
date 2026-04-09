from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import LspConnection


class RefactoringService:
    """Rename and prepare rename."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection

    async def rename(
        self, uri: str, line: int, character: int, new_name: str
    ) -> dict[str, Any] | None:
        """Rename a symbol. Returns a WorkspaceEdit."""
        return await self._connection.send_request(
            "textDocument/rename",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
                "newName": new_name,
            },
        )

    async def prepare_rename(self, uri: str, line: int, character: int) -> dict[str, Any] | None:
        """Check if rename is possible at a position. Returns the range and placeholder."""
        return await self._connection.send_request(
            "textDocument/prepareRename",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )
