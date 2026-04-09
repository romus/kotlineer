from __future__ import annotations

import logging
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import LspConnection

logger = logging.getLogger(__name__)


class DiagnosticsService:
    """Listens for textDocument/publishDiagnostics notifications and caches them.

    Also supports the pull model (``textDocument/diagnostic``) for servers
    that advertise ``diagnosticProvider`` in their capabilities.
    """

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._handlers: list[Callable[..., Any]] = []

        # Auto-subscribe to diagnostic notifications (push model)
        self._connection.on_notification("textDocument/publishDiagnostics", self._on_diagnostics)

    async def pull(self, uri: str) -> list[dict[str, Any]]:
        """Request diagnostics for a file via textDocument/diagnostic (pull model)."""
        result = await self._connection.send_request(
            "textDocument/diagnostic",
            {"textDocument": {"uri": uri}},
        )
        items = (result or {}).get("items", [])
        self._cache[uri] = items
        self._notify(uri, items)
        return items

    def get(self, uri: str | None = None) -> dict[str, list[dict[str, Any]]]:
        """Get cached diagnostics.

        If uri is given, returns {uri: diagnostics} for that file only.
        If uri is None, returns all cached diagnostics.
        """
        if uri is not None:
            diags = self._cache.get(uri, [])
            return {uri: diags}
        return dict(self._cache)

    def get_errors(self, uri: str | None = None) -> dict[str, list[dict[str, Any]]]:
        """Get only error-level diagnostics (severity=1)."""
        all_diags = self.get(uri)
        return {
            u: [d for d in diags if d.get("severity") == 1]
            for u, diags in all_diags.items()
            if any(d.get("severity") == 1 for d in diags)
        }

    def get_warnings(self, uri: str | None = None) -> dict[str, list[dict[str, Any]]]:
        """Get only warning-level diagnostics (severity=2)."""
        all_diags = self.get(uri)
        return {
            u: [d for d in diags if d.get("severity") == 2]
            for u, diags in all_diags.items()
            if any(d.get("severity") == 2 for d in diags)
        }

    def on_update(self, handler: Callable[..., Any]) -> None:
        """Register a handler called when diagnostics are updated."""
        self._handlers.append(handler)

    def clear(self) -> None:
        """Clear the diagnostics cache."""
        self._cache.clear()

    def _notify(self, uri: str, diagnostics: list[dict[str, Any]]) -> None:
        for handler in self._handlers:
            try:
                handler(uri, diagnostics)
            except Exception:
                logger.exception("Error in diagnostics handler")

    def _on_diagnostics(self, params: dict[str, Any]) -> None:
        uri = params.get("uri", "")
        diagnostics = params.get("diagnostics", [])
        self._cache[uri] = diagnostics
        logger.debug("Diagnostics updated for %s: %d items", uri, len(diagnostics))
        self._notify(uri, diagnostics)
