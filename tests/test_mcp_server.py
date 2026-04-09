from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from kotlineer.mcp_server import (
    _format_locations,
    _get_client,
    _get_workspace,
    _resolve_path,
    kotlin_check,
    kotlin_complete,
    kotlin_definition,
    kotlin_format,
    kotlin_hover,
    kotlin_references,
    kotlin_rename,
    kotlin_symbols,
)

# ── Helpers ────────────────────────────────────────────────────────


def _make_ctx(client=None, workspace=None):
    """Build a fake MCP Context with a KotlineerContext inside."""
    if client is None:
        client = MagicMock()
    if workspace is None:
        from pathlib import Path

        workspace = Path("/test/workspace")

    lifespan_ctx = MagicMock()
    lifespan_ctx.client = client
    lifespan_ctx.workspace = workspace

    request_ctx = MagicMock()
    request_ctx.lifespan_context = lifespan_ctx

    ctx = MagicMock()
    ctx.request_context = request_ctx
    return ctx


def _make_client():
    """Build a MagicMock KotlinLspClient with async service methods."""
    client = MagicMock()
    client.open_file = AsyncMock(return_value="file:///test/workspace/Main.kt")
    client.capabilities = {}

    # Diagnostics
    diag_service = MagicMock()
    diag_service.pull = AsyncMock()
    diag_service.get.return_value = {}
    diag_service.get_errors.return_value = {}
    diag_service.on_update = MagicMock()
    type(client).diagnostics = PropertyMock(return_value=diag_service)

    # Formatting
    fmt_service = MagicMock()
    fmt_service.format = AsyncMock(return_value=[])
    type(client).formatting = PropertyMock(return_value=fmt_service)

    # Hover
    hover_service = MagicMock()
    hover_service.hover = AsyncMock(return_value=None)
    type(client).hover = PropertyMock(return_value=hover_service)

    # Navigation
    nav_service = MagicMock()
    nav_service.definition = AsyncMock(return_value=None)
    nav_service.type_definition = AsyncMock(return_value=None)
    nav_service.references = AsyncMock(return_value=None)
    type(client).navigation = PropertyMock(return_value=nav_service)

    # Symbols
    sym_service = MagicMock()
    sym_service.document_symbols = AsyncMock(return_value=None)
    sym_service.workspace_symbols = AsyncMock(return_value=None)
    type(client).symbols = PropertyMock(return_value=sym_service)

    # Completion
    comp_service = MagicMock()
    comp_service.complete = AsyncMock(return_value=None)
    type(client).completion = PropertyMock(return_value=comp_service)

    # Refactoring
    ref_service = MagicMock()
    ref_service.rename = AsyncMock(return_value=None)
    type(client).refactoring = PropertyMock(return_value=ref_service)

    return client


# ── Helper tests ───────────────────────────────────────────────────


class TestHelpers:
    def test_get_client(self):
        client = MagicMock()
        ctx = _make_ctx(client=client)
        assert _get_client(ctx) is client

    def test_get_workspace(self):
        from pathlib import Path

        ws = Path("/my/workspace")
        ctx = _make_ctx(workspace=ws)
        assert _get_workspace(ctx) == ws

    def test_resolve_path_absolute(self):
        from pathlib import Path

        result = _resolve_path("/abs/path/Main.kt", Path("/workspace"))
        assert result == Path("/abs/path/Main.kt")

    def test_resolve_path_relative(self):
        from pathlib import Path

        result = _resolve_path("src/Main.kt", Path("/workspace"))
        assert result == Path("/workspace/src/Main.kt")

    def test_format_locations_empty(self):
        assert _format_locations(None) == "No results."
        assert _format_locations([]) == "No results."

    def test_format_locations_single(self):
        locs = [
            {
                "uri": "file:///src/Main.kt",
                "range": {"start": {"line": 9, "character": 4}},
            }
        ]
        result = json.loads(_format_locations(locs))
        assert len(result) == 1
        assert result[0]["file"] == "/src/Main.kt"
        assert result[0]["line"] == 10
        assert result[0]["column"] == 5

    def test_format_locations_unwraps_single(self):
        loc = {
            "uri": "file:///src/Main.kt",
            "range": {"start": {"line": 0, "character": 0}},
        }
        result = json.loads(_format_locations(loc))
        assert len(result) == 1


# ── kotlin_check ───────────────────────────────────────────────────


class TestKotlinCheck:
    async def test_no_files(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        with patch("kotlineer.mcp_server.find_kotlin_files", return_value=[]):
            result = await kotlin_check(ctx)
        assert result == "No .kt files found."

    async def test_clean(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        with (
            patch("kotlineer.mcp_server.find_kotlin_files", return_value=[]),
            patch("kotlineer.mcp_server.wait_for_diagnostics", new_callable=AsyncMock),
        ):
            # Provide explicit files so find_kotlin_files isn't called.
            client.diagnostics.get.return_value = {}
            result = await kotlin_check(ctx, files=["Main.kt"])

        assert result == "No issues found."

    async def test_diagnostics_found(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.diagnostics.get.return_value = {
            "file:///test/workspace/Main.kt": [
                {
                    "range": {"start": {"line": 4, "character": 0}},
                    "severity": 1,
                    "message": "Unresolved reference: foo",
                }
            ]
        }

        with patch("kotlineer.mcp_server.wait_for_diagnostics", new_callable=AsyncMock):
            result = await kotlin_check(ctx, files=["Main.kt"])

        parsed = json.loads(result)
        assert len(parsed) == 1
        diags = list(parsed.values())[0]
        assert diags[0]["line"] == 5
        assert diags[0]["severity"] == "error"

    async def test_errors_only(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.diagnostics.get_errors.return_value = {}

        with patch("kotlineer.mcp_server.wait_for_diagnostics", new_callable=AsyncMock):
            result = await kotlin_check(ctx, files=["Main.kt"], errors_only=True)

        client.diagnostics.get_errors.assert_called_once()
        assert result == "No issues found."


# ── kotlin_format ──────────────────────────────────────────────────


class TestKotlinFormat:
    async def test_no_changes(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        result = await kotlin_format(ctx, file="Main.kt")
        assert "No formatting changes" in result

    async def test_returns_formatted(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.formatting.format.return_value = [
            {
                "range": {
                    "start": {"line": 0, "character": 5},
                    "end": {"line": 0, "character": 11},
                },
                "newText": " world",
            }
        ]

        with patch("pathlib.Path.read_text", return_value="hello there"):
            result = await kotlin_format(ctx, file="Main.kt")

        assert result == "hello world"

    async def test_write_mode(self, tmp_path):
        client = _make_client()
        ctx = _make_ctx(client=client, workspace=tmp_path)

        kt_file = tmp_path / "Main.kt"
        kt_file.write_text("hello there")

        client.open_file.return_value = f"file://{kt_file}"
        client.formatting.format.return_value = [
            {
                "range": {
                    "start": {"line": 0, "character": 5},
                    "end": {"line": 0, "character": 11},
                },
                "newText": " world",
            }
        ]

        result = await kotlin_format(ctx, file="Main.kt", write=True)
        assert "Formatted and saved" in result
        assert kt_file.read_text() == "hello world"


# ── kotlin_hover ───────────────────────────────────────────────────


class TestKotlinHover:
    async def test_no_hover(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        result = await kotlin_hover(ctx, file="Main.kt", line=1, column=1)
        assert "No hover information" in result

    async def test_markup_content(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.hover.hover.return_value = {
            "contents": {"kind": "markdown", "value": "fun main(): Unit"}
        }

        result = await kotlin_hover(ctx, file="Main.kt", line=5, column=10)
        assert "fun main(): Unit" in result

    async def test_position_conversion(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        await kotlin_hover(ctx, file="Main.kt", line=10, column=5)
        client.hover.hover.assert_called_once()
        args = client.hover.hover.call_args
        # 1-based -> 0-based
        assert args[0][1] == 9  # line
        assert args[0][2] == 4  # column


# ── kotlin_definition ──────────────────────────────────────────────


class TestKotlinDefinition:
    async def test_no_result(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        result = await kotlin_definition(ctx, file="Main.kt", line=1, column=1)
        assert "No results" in result

    async def test_definition(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.navigation.definition.return_value = [
            {
                "uri": "file:///src/Utils.kt",
                "range": {"start": {"line": 9, "character": 4}},
            }
        ]

        result = await kotlin_definition(ctx, file="Main.kt", line=5, column=10)
        parsed = json.loads(result)
        assert parsed[0]["file"] == "/src/Utils.kt"
        assert parsed[0]["line"] == 10

    async def test_type_definition(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.navigation.type_definition.return_value = [
            {
                "uri": "file:///src/Types.kt",
                "range": {"start": {"line": 0, "character": 0}},
            }
        ]

        result = await kotlin_definition(
            ctx, file="Main.kt", line=1, column=1, kind="type_definition"
        )
        parsed = json.loads(result)
        assert parsed[0]["file"] == "/src/Types.kt"


# ── kotlin_references ─────────────────────────────────────────────


class TestKotlinReferences:
    async def test_no_references(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        result = await kotlin_references(ctx, file="Main.kt", line=1, column=1)
        assert "No results" in result

    async def test_found(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.navigation.references.return_value = [
            {"uri": "file:///a.kt", "range": {"start": {"line": 0, "character": 0}}},
            {"uri": "file:///b.kt", "range": {"start": {"line": 5, "character": 2}}},
        ]

        result = await kotlin_references(ctx, file="Main.kt", line=1, column=1)
        parsed = json.loads(result)
        assert len(parsed) == 2


# ── kotlin_symbols ─────────────────────────────────────────────────


class TestKotlinSymbols:
    async def test_no_params(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        result = await kotlin_symbols(ctx)
        assert "Error" in result

    async def test_document_symbols(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.symbols.document_symbols.return_value = [
            {"name": "main", "kind": 12, "range": {"start": {"line": 0}}}
        ]

        result = await kotlin_symbols(ctx, file="Main.kt")
        parsed = json.loads(result)
        assert parsed[0]["name"] == "main"

    async def test_workspace_symbols(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.symbols.workspace_symbols.return_value = [{"name": "UserService", "kind": 5}]

        result = await kotlin_symbols(ctx, query="UserService")
        parsed = json.loads(result)
        assert parsed[0]["name"] == "UserService"


# ── kotlin_complete ────────────────────────────────────────────────


class TestKotlinComplete:
    async def test_no_completions(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        result = await kotlin_complete(ctx, file="Main.kt", line=1, column=1)
        assert "No completions" in result

    async def test_completion_list(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.completion.complete.return_value = {
            "items": [
                {"label": "println", "kind": 3, "detail": "(message: Any?)"},
                {"label": "print", "kind": 3},
            ]
        }

        result = await kotlin_complete(ctx, file="Main.kt", line=1, column=1)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["label"] == "println"
        assert parsed[0]["detail"] == "(message: Any?)"

    async def test_completion_array(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.completion.complete.return_value = [
            {"label": "foo", "kind": 6},
        ]

        result = await kotlin_complete(ctx, file="Main.kt", line=1, column=1)
        parsed = json.loads(result)
        assert len(parsed) == 1


# ── kotlin_rename ──────────────────────────────────────────────────


class TestKotlinRename:
    async def test_not_available(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        result = await kotlin_rename(ctx, file="Main.kt", line=1, column=1, new_name="newName")
        assert "not available" in result

    async def test_rename_changes(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.refactoring.rename.return_value = {
            "changes": {
                "file:///test/Main.kt": [{"range": {}, "newText": "newName"}],
                "file:///test/Utils.kt": [
                    {"range": {}, "newText": "newName"},
                    {"range": {}, "newText": "newName"},
                ],
            }
        }

        result = await kotlin_rename(ctx, file="Main.kt", line=1, column=1, new_name="newName")
        parsed = json.loads(result)
        assert parsed["renamed_to"] == "newName"
        assert len(parsed["files_changed"]) == 2

    async def test_rename_document_changes(self):
        client = _make_client()
        ctx = _make_ctx(client=client)

        client.refactoring.rename.return_value = {
            "documentChanges": [
                {
                    "textDocument": {"uri": "file:///test/Main.kt"},
                    "edits": [{"range": {}, "newText": "x"}],
                }
            ]
        }

        result = await kotlin_rename(ctx, file="Main.kt", line=1, column=1, new_name="x")
        parsed = json.loads(result)
        assert parsed["renamed_to"] == "x"
        assert len(parsed["files_changed"]) == 1
