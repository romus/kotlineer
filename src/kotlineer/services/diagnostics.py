from __future__ import annotations

import logging
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..connection import LspConnection

logger = logging.getLogger(__name__)


class DiagnosticsService:
    """Listens for textDocument/publishDiagnostics notifications and caches them."""

    def __init__(self, connection: LspConnection) -> None:
        self._connection = connection
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._handlers: list[Callable[..., Any]] = []

        # Auto-subscribe to diagnostic notifications
        self._connection.on_notification("textDocument/publishDiagnostics", self._on_diagnostics)

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

    def _on_diagnostics(self, params: dict[str, Any]) -> None:
        uri = params.get("uri", "")
        diagnostics = params.get("diagnostics", [])
        self._cache[uri] = diagnostics
        logger.debug("Diagnostics updated for %s: %d items", uri, len(diagnostics))

        for handler in self._handlers:
            try:
                handler(uri, diagnostics)
            except Exception:
                logger.exception("Error in diagnostics handler")
