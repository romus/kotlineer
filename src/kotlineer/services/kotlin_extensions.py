from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import LspConnection


class KotlinExtensionService:
    """Custom kotlin/* LSP methods specific to kotlin-language-server."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection

    async def jar_class_contents(self, uri: str) -> str | None:
        """Get the contents of a JAR class file by its URI."""
        return await self._connection.send_request(
            "kotlin/jarClassContents",
            {"uri": uri},
        )

    async def build_output_location(self) -> str | None:
        """Get the file path where build output is generated."""
        return await self._connection.send_request(
            "kotlin/buildOutputLocation",
            {},
        )

    async def main_class(self, uri: str) -> dict[str, Any] | None:
        """Get the main class associated with a document."""
        return await self._connection.send_request(
            "kotlin/mainClass",
            {"uri": uri},
        )

    async def override_member(
        self, uri: str, line: int, character: int
    ) -> list[dict[str, Any]] | None:
        """Generate code for overriding/implementing members at a position."""
        return await self._connection.send_request(
            "kotlin/overrideMember",
            {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": character},
            },
        )
