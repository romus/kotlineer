from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .types import OpenDocument

if TYPE_CHECKING:
    from .connection import LspConnection

logger = logging.getLogger(__name__)


class DocumentManager:
    """Tracks open documents and sends didOpen/didChange/didClose notifications."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection
        self._documents: dict[str, OpenDocument] = {}

    async def open(self, uri: str, content: str, language_id: str = "kotlin") -> None:
        """Open a document in the LSP session."""
        if uri in self._documents:
            # Already open — update instead
            await self.update(uri, content)
            return

        doc = OpenDocument(uri=uri, content=content, version=1, language_id=language_id)
        self._documents[uri] = doc

        await self._connection.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": language_id,
                    "version": doc.version,
                    "text": content,
                }
            },
        )
        logger.debug("Opened document: %s", uri)

    async def update(self, uri: str, content: str) -> None:
        """Update an open document's content (full sync)."""
        doc = self._documents.get(uri)
        if doc is None:
            # Auto-open if not tracked
            await self.open(uri, content)
            return

        doc.version += 1
        doc.content = content

        await self._connection.send_notification(
            "textDocument/didChange",
            {
                "textDocument": {"uri": uri, "version": doc.version},
                "contentChanges": [{"text": content}],
            },
        )
        logger.debug("Updated document: %s (version=%d)", uri, doc.version)

    async def close(self, uri: str) -> None:
        """Close a document in the LSP session."""
        if uri not in self._documents:
            return

        del self._documents[uri]

        await self._connection.send_notification(
            "textDocument/didClose",
            {"textDocument": {"uri": uri}},
        )
        logger.debug("Closed document: %s", uri)

    async def save(self, uri: str) -> None:
        """Notify the server that a document was saved."""
        doc = self._documents.get(uri)
        if doc is None:
            return

        await self._connection.send_notification(
            "textDocument/didSave",
            {
                "textDocument": {"uri": uri},
                "text": doc.content,
            },
        )

    def get(self, uri: str) -> OpenDocument | None:
        return self._documents.get(uri)

    def get_all(self) -> list[OpenDocument]:
        return list(self._documents.values())

    async def close_all(self) -> None:
        """Close all open documents."""
        for uri in list(self._documents.keys()):
            await self.close(uri)
