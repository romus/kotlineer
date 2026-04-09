from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..connection import LspConnection


class CompletionService:
    """Code completion."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection

    async def complete(
        self, uri: str, line: int, character: int
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Get completion suggestions at a position.

        Returns a CompletionList dict or a list of CompletionItem dicts.
        """
        return await self._connection.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )

    async def resolve(self, item: dict[str, Any]) -> dict[str, Any]:
        """Resolve additional details for a completion item."""
        return await self._connection.send_request(
            "completionItem/resolve",
            item,
        )
