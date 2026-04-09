from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Config ──────────────────────────────────────────────────────────


@dataclass
class KotlinLspConfig:
    """Configuration for the Kotlin LSP client (JetBrains kotlin-lsp)."""

    server_path: str
    """Path to the kotlin-lsp binary."""

    workspace_root: str
    """Absolute path to the project root directory."""

    server_args: list[str] = field(default_factory=list)
    """Extra CLI arguments for the server process."""

    server_env: dict[str, str] = field(default_factory=dict)
    """Extra environment variables for the server process."""

    request_timeout: float = 30.0
    """Timeout in seconds for LSP requests."""

    def to_initialization_options(self) -> dict[str, Any]:
        """Build the initializationOptions dict for the LSP initialize request."""
        return {}


# ── Open document state ─────────────────────────────────────────────


@dataclass
class OpenDocument:
    """Represents a document currently open in the LSP session."""

    uri: str
    content: str
    version: int
    language_id: str = "kotlin"


# ── Errors ──────────────────────────────────────────────────────────


class LspError(Exception):
    """Base class for LSP-related errors."""

    def __init__(self, message: str, code: int = -1, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class ServerNotRunningError(LspError):
    """Raised when a request is made but the server is not running."""

    def __init__(self) -> None:
        super().__init__("LSP server is not running", code=-1)


class RequestTimeoutError(LspError):
    """Raised when an LSP request times out."""

    def __init__(self, method: str, timeout: float) -> None:
        super().__init__(
            f"Request '{method}' timed out after {timeout}s",
            code=-2,
        )
        self.method = method
        self.timeout = timeout


class ServerCrashedError(LspError):
    """Raised when the LSP server process crashes unexpectedly."""

    def __init__(self, exit_code: int | None = None) -> None:
        msg = "LSP server crashed"
        if exit_code is not None:
            msg += f" (exit code {exit_code})"
        super().__init__(msg, code=-3)
        self.exit_code = exit_code
