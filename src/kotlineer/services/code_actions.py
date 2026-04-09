from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..connection import LspConnection


class CodeActionService:
    """Code actions (quick fixes, refactorings) and code lens."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection

    async def get_actions(
        self,
        uri: str,
        start_line: int,
        start_character: int,
        end_line: int,
        end_character: int,
        diagnostics: list[dict[str, Any]] | None = None,
        only: list[str] | None = None,
    ) -> list[dict[str, Any]] | None:
        """Get code actions for a range.

        Args:
            only: Filter by code action kinds (e.g. ["quickfix", "refactor"])
        """
        context: dict[str, Any] = {"diagnostics": diagnostics or []}
        if only:
            context["only"] = only

        return await self._connection.send_request(
            "textDocument/codeAction",
            {
                "textDocument": {"uri": uri},
                "range": {
                    "start": {"line": start_line, "character": start_character},
                    "end": {"line": end_line, "character": end_character},
                },
                "context": context,
            },
        )

    async def resolve(self, action: dict[str, Any]) -> dict[str, Any]:
        """Resolve additional details for a code action (e.g. the edit)."""
        return await self._connection.send_request(
            "codeAction/resolve",
            action,
        )

    async def code_lens(self, uri: str) -> list[dict[str, Any]] | None:
        """Get code lens items for a document."""
        return await self._connection.send_request(
            "textDocument/codeLens",
            {"textDocument": {"uri": uri}},
        )

    async def code_lens_resolve(self, lens: dict[str, Any]) -> dict[str, Any]:
        """Resolve a code lens item."""
        return await self._connection.send_request(
            "codeLens/resolve",
            lens,
        )
