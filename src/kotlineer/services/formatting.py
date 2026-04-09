from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import LspConnection


class FormattingService:
    """Document formatting."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection

    async def format(
        self, uri: str, tab_size: int = 4, insert_spaces: bool = True
    ) -> list[dict[str, Any]] | None:
        """Format the entire document. Returns a list of TextEdits."""
        return await self._connection.send_request(
            "textDocument/formatting",
            {
                "textDocument": {"uri": uri},
                "options": {
                    "tabSize": tab_size,
                    "insertSpaces": insert_spaces,
                },
            },
        )

    async def format_range(
        self,
        uri: str,
        start_line: int,
        start_character: int,
        end_line: int,
        end_character: int,
        tab_size: int = 4,
        insert_spaces: bool = True,
    ) -> list[dict[str, Any]] | None:
        """Format a range within the document. Returns a list of TextEdits."""
        return await self._connection.send_request(
            "textDocument/rangeFormatting",
            {
                "textDocument": {"uri": uri},
                "range": {
                    "start": {"line": start_line, "character": start_character},
                    "end": {"line": end_line, "character": end_character},
                },
                "options": {
                    "tabSize": tab_size,
                    "insertSpaces": insert_spaces,
                },
            },
        )
