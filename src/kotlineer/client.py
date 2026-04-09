from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote
from functools import cached_property

from .connection import LspConnection
from .documents import DocumentManager
from .process import ServerProcess
from .services.code_actions import CodeActionService
from .services.completion import CompletionService
from .services.diagnostics import DiagnosticsService
from .services.formatting import FormattingService
from .services.hierarchy import HierarchyService
from .services.hover import HoverService
from .services.kotlin_extensions import KotlinExtensionService
from .services.navigation import NavigationService
from .services.refactoring import RefactoringService
from .services.symbols import SymbolService
from .types import KotlinLspConfig, ServerNotRunningError

logger = logging.getLogger(__name__)


def _path_to_uri(path: str) -> str:
    """Convert an absolute file path to a file:// URI."""
    p = Path(path).resolve()
    return "file://" + quote(str(p), safe="/:")


class KotlinLspClient:
    """Main facade for interacting with kotlin-language-server."""

    def __init__(
        self,
        server_path: str,
        workspace_root: str,
        **kwargs: Any,
    ) -> None:
        self._config = KotlinLspConfig(
            server_path=server_path,
            workspace_root=str(Path(workspace_root).resolve()),
            **kwargs,
        )
        self._server = ServerProcess(self._config)
        self._connection: LspConnection | None = None
        self._documents: DocumentManager | None = None
        self._capabilities: dict[str, Any] | None = None

        # Cached service instances (reset on stop)
        self._services: dict[str, Any] = {}

    @property
    def is_running(self) -> bool:
        return self._server.is_running and self._connection is not None

    @property
    def capabilities(self) -> dict[str, Any] | None:
        return self._capabilities

    # ── Lifecycle ───────────────────────────────────────────────────

    async def start(self) -> dict[str, Any]:
        """Start the server and perform LSP initialization. Returns server capabilities."""
        stdout, stdin = await self._server.start()

        self._connection = LspConnection(
            reader=stdout,
            writer=stdin,
            request_timeout=self._config.request_timeout,
        )
        await self._connection.start()

        self._documents = DocumentManager(self._connection)

        # LSP initialize handshake
        workspace_uri = _path_to_uri(self._config.workspace_root)
        init_result = await self._connection.send_request(
            "initialize",
            {
                "processId": None,
                "rootUri": workspace_uri,
                "capabilities": self._client_capabilities(),
                "initializationOptions": self._config.to_initialization_options(),
                "workspaceFolders": [
                    {"uri": workspace_uri, "name": Path(self._config.workspace_root).name}
                ],
            },
        )

        self._capabilities = init_result.get("capabilities", {}) if init_result else {}

        # Send initialized notification
        await self._connection.send_notification("initialized", {})

        logger.info("LSP initialized. Capabilities: %s", list(self._capabilities.keys()))
        return self._capabilities

    async def stop(self) -> None:
        """Shutdown the LSP session and stop the server."""
        if self._documents:
            await self._documents.close_all()

        if self._connection:
            try:
                await self._connection.send_request("shutdown")
                await self._connection.send_notification("exit")
            except Exception:
                logger.debug("Error during LSP shutdown", exc_info=True)
            await self._connection.close()

        await self._server.stop()

        self._connection = None
        self._documents = None
        self._capabilities = None
        self._services.clear()

        logger.info("LSP client stopped")

    # ── Document helpers ────────────────────────────────────────────

    async def open_file(self, path: str) -> str:
        """Open a file from disk in the LSP session. Returns the file URI."""
        self._ensure_running()
        p = Path(path)
        if not p.is_absolute():
            p = Path(self._config.workspace_root) / p
        p = p.resolve()

        uri = _path_to_uri(str(p))
        content = p.read_text(encoding="utf-8")
        assert self._documents is not None
        await self._documents.open(uri, content)
        return uri

    async def update_file(self, path: str, content: str) -> str:
        """Update an open file's content. Returns the file URI."""
        self._ensure_running()
        p = Path(path)
        if not p.is_absolute():
            p = Path(self._config.workspace_root) / p
        uri = _path_to_uri(str(p.resolve()))
        assert self._documents is not None
        await self._documents.update(uri, content)
        return uri

    async def close_file(self, path: str) -> None:
        """Close a file in the LSP session."""
        self._ensure_running()
        p = Path(path)
        if not p.is_absolute():
            p = Path(self._config.workspace_root) / p
        uri = _path_to_uri(str(p.resolve()))
        assert self._documents is not None
        await self._documents.close(uri)

    # ── Services ────────────────────────────────────────────────────

    @property
    def completion(self) -> CompletionService:
        return self._get_service("completion", CompletionService)

    @property
    def hover(self) -> HoverService:
        return self._get_service("hover", HoverService)

    @property
    def navigation(self) -> NavigationService:
        return self._get_service("navigation", NavigationService)

    @property
    def symbols(self) -> SymbolService:
        return self._get_service("symbols", SymbolService)

    @property
    def formatting(self) -> FormattingService:
        return self._get_service("formatting", FormattingService)

    @property
    def code_actions(self) -> CodeActionService:
        return self._get_service("code_actions", CodeActionService)

    @property
    def refactoring(self) -> RefactoringService:
        return self._get_service("refactoring", RefactoringService)

    @property
    def hierarchy(self) -> HierarchyService:
        return self._get_service("hierarchy", HierarchyService)

    @property
    def kotlin(self) -> KotlinExtensionService:
        return self._get_service("kotlin", KotlinExtensionService)

    @property
    def diagnostics(self) -> DiagnosticsService:
        return self._get_service("diagnostics", DiagnosticsService)

    # ── Events ──────────────────────────────────────────────────────

    def on_diagnostics(self, handler: Callable[..., Any]) -> None:
        """Register a handler for diagnostic notifications."""
        self._ensure_running()
        assert self._connection is not None
        self._connection.on_notification("textDocument/publishDiagnostics", handler)

    # ── Internal ────────────────────────────────────────────────────

    def _ensure_running(self) -> None:
        if not self.is_running:
            raise ServerNotRunningError()

    def _get_service(self, name: str, cls: type) -> Any:
        self._ensure_running()
        if name not in self._services:
            assert self._connection is not None
            self._services[name] = cls(self._connection)
        return self._services[name]

    def _client_capabilities(self) -> dict[str, Any]:
        """Build client capabilities for the initialize request."""
        return {
            "textDocument": {
                "synchronization": {
                    "dynamicRegistration": False,
                    "willSave": False,
                    "willSaveWaitUntil": False,
                    "didSave": True,
                },
                "completion": {
                    "completionItem": {
                        "snippetSupport": self._config.snippets_enabled,
                        "commitCharactersSupport": True,
                        "documentationFormat": ["plaintext", "markdown"],
                        "deprecatedSupport": True,
                        "preselectSupport": True,
                        "resolveSupport": {"properties": ["documentation", "detail"]},
                    },
                    "contextSupport": True,
                },
                "hover": {
                    "contentFormat": ["plaintext", "markdown"],
                },
                "signatureHelp": {
                    "signatureInformation": {
                        "documentationFormat": ["plaintext", "markdown"],
                        "parameterInformation": {"labelOffsetSupport": True},
                    },
                },
                "definition": {"dynamicRegistration": False, "linkSupport": True},
                "typeDefinition": {"dynamicRegistration": False, "linkSupport": True},
                "implementation": {"dynamicRegistration": False, "linkSupport": True},
                "references": {"dynamicRegistration": False},
                "documentSymbol": {
                    "hierarchicalDocumentSymbolSupport": True,
                },
                "codeAction": {
                    "codeActionLiteralSupport": {
                        "codeActionKind": {
                            "valueSet": [
                                "quickfix",
                                "refactor",
                                "refactor.extract",
                                "refactor.inline",
                                "refactor.rewrite",
                                "source",
                                "source.organizeImports",
                            ]
                        }
                    },
                    "resolveSupport": {"properties": ["edit"]},
                },
                "formatting": {"dynamicRegistration": False},
                "rangeFormatting": {"dynamicRegistration": False},
                "rename": {"prepareSupport": True},
                "publishDiagnostics": {"relatedInformation": True},
                "callHierarchy": {"dynamicRegistration": False},
                "typeHierarchy": {"dynamicRegistration": False},
                "codeLens": {"dynamicRegistration": False},
                "foldingRange": {"dynamicRegistration": False},
                "documentHighlight": {"dynamicRegistration": False},
                "selectionRange": {"dynamicRegistration": False},
                "inlayHint": {"dynamicRegistration": False},
                "semanticTokens": {
                    "dynamicRegistration": False,
                    "requests": {"full": True, "range": False},
                    "tokenTypes": [],
                    "tokenModifiers": [],
                    "formats": ["relative"],
                },
            },
            "workspace": {
                "workspaceFolders": True,
                "symbol": {"dynamicRegistration": False},
                "configuration": True,
                "didChangeConfiguration": {"dynamicRegistration": False},
            },
        }
