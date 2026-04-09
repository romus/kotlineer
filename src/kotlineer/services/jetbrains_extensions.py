from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import LspConnection


class JetBrainsExtensionService:
    """Custom JetBrains-specific LSP methods for kotlin-lsp."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection

    async def restart_lsp(self) -> None:
        """Restart the Kotlin LSP server."""
        await self._connection.send_request(
            "jetbrains.kotlin.restartLsp",
            {},
        )
