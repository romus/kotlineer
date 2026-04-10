"""MCP server exposing kotlin-lsp capabilities as tools for AI assistants."""

from __future__ import annotations

import argparse
import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from .client import KotlinLspClient
from .types import LspError, RequestTimeoutError, ServerNotRunningError
from .utils import (
    SEVERITY_LABELS,
    apply_text_edits,
    find_kotlin_files,
    uri_to_path,
    wait_for_diagnostics,
)

logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────


@dataclass
class KotlineerContext:
    """Shared state available to all MCP tool handlers."""

    client: KotlinLspClient
    workspace: Path


# Module-level config set by main() before server starts.
_config: argparse.Namespace | None = None


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[KotlineerContext]:
    assert _config is not None, "Server config not set. Call main() or run_server()."

    workspace = Path(_config.workspace).resolve()

    if _config.connect:
        host, port_str = _config.connect.rsplit(":", 1)
        client = KotlinLspClient(
            str(workspace),
            host=host,
            port=int(port_str),
            request_timeout=_config.timeout,
        )
    else:
        client = KotlinLspClient.spawn(
            str(workspace),
            server_path=_config.server_path,
            request_timeout=_config.timeout,
        )

    await client.start()
    logger.info("kotlin-lsp started for workspace: %s", workspace)
    try:
        yield KotlineerContext(client=client, workspace=workspace)
    finally:
        await client.stop()
        logger.info("kotlin-lsp stopped")


mcp = FastMCP("kotlineer", lifespan=_lifespan)

CtxType = Context[ServerSession, KotlineerContext]


# ── Helpers ────────────────────────────────────────────────────────


def _get_client(ctx: CtxType) -> KotlinLspClient:
    return ctx.request_context.lifespan_context.client


def _get_workspace(ctx: CtxType) -> Path:
    return ctx.request_context.lifespan_context.workspace


def _resolve_path(file: str, workspace: Path) -> Path:
    p = Path(file)
    if not p.is_absolute():
        p = workspace / p
    return p.resolve()


def _format_locations(result: Any) -> str:
    if not result:
        return "No results."
    locations = result if isinstance(result, list) else [result]
    output = []
    for loc in locations:
        path = uri_to_path(loc["uri"])
        line = loc["range"]["start"]["line"] + 1
        col = loc["range"]["start"]["character"] + 1
        output.append({"file": path, "line": line, "column": col})
    return json.dumps(output, indent=2, ensure_ascii=False)


# ── Tools ──────────────────────────────────────────────────────────


@mcp.tool()
async def kotlin_check(
    ctx: CtxType,
    files: list[str] | None = None,
    errors_only: bool = False,
) -> str:
    """Check Kotlin files for errors and warnings.

    Args:
        files: List of file paths to check. If not provided, checks all .kt files in workspace.
        errors_only: If true, only report errors (skip warnings, info, hints).

    Returns:
        JSON with diagnostics grouped by file.
        Each diagnostic has: file, line, column, severity, message.
    """
    client = _get_client(ctx)
    workspace = _get_workspace(ctx)

    try:
        if files:
            paths = [_resolve_path(f, workspace) for f in files]
        else:
            paths = find_kotlin_files(workspace)

        if not paths:
            return "No .kt files found."

        # Ensure diagnostics service is ready before opening files.
        _ = client.diagnostics

        uris: list[str] = []
        for p in paths:
            uris.append(await client.open_file(str(p)))

        # Pull or wait for diagnostics.
        caps = client.capabilities or {}
        if caps.get("diagnosticProvider"):
            for uri in uris:
                await client.diagnostics.pull(uri)
        else:
            await wait_for_diagnostics(client, timeout=30.0, settle=3.0)

        all_diags = client.diagnostics.get_errors() if errors_only else client.diagnostics.get()

        output: dict[str, Any] = {}
        for uri, diags in all_diags.items():
            if not diags:
                continue
            path = uri_to_path(uri)
            output[path] = [
                {
                    "line": d["range"]["start"]["line"] + 1,
                    "column": d["range"]["start"]["character"] + 1,
                    "severity": SEVERITY_LABELS.get(d.get("severity", 1), "error"),
                    "message": d.get("message", ""),
                }
                for d in diags
            ]

        if not output:
            return "No issues found."
        return json.dumps(output, indent=2, ensure_ascii=False)

    except (FileNotFoundError, RequestTimeoutError, ServerNotRunningError, LspError) as e:
        return f"Error: {e}"


@mcp.tool()
async def kotlin_format(
    ctx: CtxType,
    file: str,
    write: bool = False,
) -> str:
    """Format a Kotlin file.

    Args:
        file: Path to the Kotlin file to format.
        write: If true, write formatted content back to disk.
            If false, return the formatted content.

    Returns:
        The formatted file content, or a message if no changes are needed.
    """
    client = _get_client(ctx)
    workspace = _get_workspace(ctx)

    try:
        path = _resolve_path(file, workspace)
        uri = await client.open_file(str(path))
        edits = await client.formatting.format(uri)

        if not edits:
            return "No formatting changes needed."

        original = path.read_text(encoding="utf-8")
        formatted = apply_text_edits(original, edits)

        if original == formatted:
            return "No formatting changes needed."

        if write:
            path.write_text(formatted, encoding="utf-8")
            return f"Formatted and saved: {path}"

        return formatted

    except (FileNotFoundError, RequestTimeoutError, ServerNotRunningError, LspError) as e:
        return f"Error: {e}"


@mcp.tool()
async def kotlin_hover(
    ctx: CtxType,
    file: str,
    line: int,
    column: int,
) -> str:
    """Get type information and documentation for a symbol at a position.

    Args:
        file: Path to the Kotlin file.
        line: Line number (1-based).
        column: Column number (1-based).

    Returns:
        Type information and documentation as text/markdown.
    """
    client = _get_client(ctx)
    workspace = _get_workspace(ctx)

    try:
        path = _resolve_path(file, workspace)
        uri = await client.open_file(str(path))
        result = await client.hover.hover(uri, line - 1, column - 1)

        if not result:
            return "No hover information available at this position."

        contents = result.get("contents", {})
        if isinstance(contents, dict):
            return str(contents.get("value", ""))
        if isinstance(contents, str):
            return contents
        if isinstance(contents, list):
            parts = []
            for item in contents:
                parts.append(item.get("value", item) if isinstance(item, dict) else item)
            return "\n".join(parts)
        return json.dumps(result, indent=2, ensure_ascii=False)

    except (FileNotFoundError, RequestTimeoutError, ServerNotRunningError, LspError) as e:
        return f"Error: {e}"


@mcp.tool()
async def kotlin_definition(
    ctx: CtxType,
    file: str,
    line: int,
    column: int,
    kind: str = "definition",
) -> str:
    """Go to the definition or type definition of a symbol.

    Args:
        file: Path to the Kotlin file.
        line: Line number (1-based).
        column: Column number (1-based).
        kind: Either "definition" (default) or "type_definition".

    Returns:
        JSON list of locations (file, line, column) where the symbol is defined.
    """
    client = _get_client(ctx)
    workspace = _get_workspace(ctx)

    try:
        path = _resolve_path(file, workspace)
        uri = await client.open_file(str(path))

        if kind == "type_definition":
            result = await client.navigation.type_definition(uri, line - 1, column - 1)
        else:
            result = await client.navigation.definition(uri, line - 1, column - 1)

        return _format_locations(result)

    except (FileNotFoundError, RequestTimeoutError, ServerNotRunningError, LspError) as e:
        return f"Error: {e}"


@mcp.tool()
async def kotlin_references(
    ctx: CtxType,
    file: str,
    line: int,
    column: int,
) -> str:
    """Find all references to a symbol.

    Args:
        file: Path to the Kotlin file.
        line: Line number (1-based).
        column: Column number (1-based).

    Returns:
        JSON list of locations (file, line, column) where the symbol is referenced.
    """
    client = _get_client(ctx)
    workspace = _get_workspace(ctx)

    try:
        path = _resolve_path(file, workspace)
        uri = await client.open_file(str(path))
        result = await client.navigation.references(uri, line - 1, column - 1)
        return _format_locations(result)

    except (FileNotFoundError, RequestTimeoutError, ServerNotRunningError, LspError) as e:
        return f"Error: {e}"


@mcp.tool()
async def kotlin_symbols(
    ctx: CtxType,
    file: str | None = None,
    query: str | None = None,
) -> str:
    """List symbols in a file or search symbols across the workspace.

    Provide either `file` for document symbols or `query` for workspace-wide symbol search.

    Args:
        file: Path to a Kotlin file (for document symbols).
        query: Search query (for workspace symbol search).

    Returns:
        JSON list of symbols with name, kind, and location.
    """
    client = _get_client(ctx)
    workspace = _get_workspace(ctx)

    if not file and not query:
        return "Error: Provide either 'file' or 'query' parameter."

    try:
        if query:
            result = await client.symbols.workspace_symbols(query)
        else:
            assert file is not None
            path = _resolve_path(file, workspace)
            uri = await client.open_file(str(path))
            result = await client.symbols.document_symbols(uri)

        if not result:
            return "No symbols found."

        return json.dumps(result, indent=2, ensure_ascii=False)

    except (FileNotFoundError, RequestTimeoutError, ServerNotRunningError, LspError) as e:
        return f"Error: {e}"


@mcp.tool()
async def kotlin_complete(
    ctx: CtxType,
    file: str,
    line: int,
    column: int,
) -> str:
    """Get code completion suggestions at a position.

    Args:
        file: Path to the Kotlin file.
        line: Line number (1-based).
        column: Column number (1-based).

    Returns:
        JSON list of completion items with label, kind, and detail.
    """
    client = _get_client(ctx)
    workspace = _get_workspace(ctx)

    try:
        path = _resolve_path(file, workspace)
        uri = await client.open_file(str(path))
        result = await client.completion.complete(uri, line - 1, column - 1)

        if not result:
            return "No completions available."

        # Normalize: CompletionList has .items, or it's already a list.
        items = result.get("items", result) if isinstance(result, dict) else result

        # Return a simplified view.
        completions = []
        for item in items:
            entry: dict[str, Any] = {"label": item.get("label", "")}
            if item.get("detail"):
                entry["detail"] = item["detail"]
            if item.get("kind"):
                entry["kind"] = item["kind"]
            completions.append(entry)

        return json.dumps(completions, indent=2, ensure_ascii=False)

    except (FileNotFoundError, RequestTimeoutError, ServerNotRunningError, LspError) as e:
        return f"Error: {e}"


@mcp.tool()
async def kotlin_rename(
    ctx: CtxType,
    file: str,
    line: int,
    column: int,
    new_name: str,
) -> str:
    """Rename a symbol across the project.

    Args:
        file: Path to the Kotlin file containing the symbol.
        line: Line number of the symbol (1-based).
        column: Column number of the symbol (1-based).
        new_name: The new name for the symbol.

    Returns:
        JSON summary of the workspace edit (files changed and number of edits per file).
    """
    client = _get_client(ctx)
    workspace = _get_workspace(ctx)

    try:
        path = _resolve_path(file, workspace)
        uri = await client.open_file(str(path))
        result = await client.refactoring.rename(uri, line - 1, column - 1, new_name)

        if not result:
            return "Rename not available at this position."

        # Summarize the workspace edit.
        changes = result.get("changes", {})
        document_changes = result.get("documentChanges", [])

        summary: dict[str, int] = {}
        if changes:
            for change_uri, edits in changes.items():
                summary[uri_to_path(change_uri)] = len(edits)
        elif document_changes:
            for doc_change in document_changes:
                change_uri = doc_change.get("textDocument", {}).get("uri", "")
                edits = doc_change.get("edits", [])
                summary[uri_to_path(change_uri)] = len(edits)

        return json.dumps(
            {"renamed_to": new_name, "files_changed": summary},
            indent=2,
            ensure_ascii=False,
        )

    except (FileNotFoundError, RequestTimeoutError, ServerNotRunningError, LspError) as e:
        return f"Error: {e}"


# ── Entry point ────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="kotlineer-mcp",
        description="MCP server for kotlin-lsp",
    )
    parser.add_argument(
        "-w",
        "--workspace",
        default=os.environ.get("KOTLINEER_WORKSPACE", "."),
        help="Project root directory (env: KOTLINEER_WORKSPACE, default: cwd)",
    )
    parser.add_argument(
        "--server-path",
        default=os.environ.get("KOTLINEER_SERVER", "kotlin-lsp"),
        help="Path to kotlin-lsp binary (env: KOTLINEER_SERVER)",
    )
    parser.add_argument(
        "--connect",
        default=None,
        help="Connect to a running kotlin-lsp at host:port instead of spawning",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="LSP request timeout in seconds (default: 30)",
    )
    return parser.parse_args()


def run_server(args: argparse.Namespace | None = None) -> None:
    """Start the MCP server. Called from CLI subcommand or standalone entry point."""
    global _config
    _config = args or _parse_args()
    mcp.run(transport="stdio")


def main() -> None:
    """Standalone entry point for kotlineer-mcp."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    run_server()
