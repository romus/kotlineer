from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from kotlineer.services.completion import CompletionService
from kotlineer.services.diagnostics import DiagnosticsService
from kotlineer.services.formatting import FormattingService
from kotlineer.services.hover import HoverService
from kotlineer.services.navigation import NavigationService
from kotlineer.services.symbols import SymbolService
from kotlineer.services.code_actions import CodeActionService
from kotlineer.services.hierarchy import HierarchyService
from kotlineer.services.refactoring import RefactoringService
from kotlineer.services.kotlin_extensions import KotlinExtensionService


def _mock_conn(return_value=None) -> AsyncMock:
    conn = AsyncMock()
    conn.send_request = AsyncMock(return_value=return_value)
    conn.on_notification = MagicMock()
    return conn


# ── Completion ─────────────────────────────────────────────────────


class TestCompletionService:
    async def test_complete(self):
        conn = _mock_conn(return_value={"isIncomplete": False, "items": []})
        svc = CompletionService(conn)

        result = await svc.complete("file:///a.kt", 10, 5)

        conn.send_request.assert_called_once_with(
            "textDocument/completion",
            {
                "textDocument": {"uri": "file:///a.kt"},
                "position": {"line": 10, "character": 5},
            },
        )
        assert result == {"isIncomplete": False, "items": []}

    async def test_resolve(self):
        item = {"label": "println", "kind": 3}
        conn = _mock_conn(return_value={**item, "detail": "fun println()"})
        svc = CompletionService(conn)

        result = await svc.resolve(item)
        conn.send_request.assert_called_once_with("completionItem/resolve", item)
        assert result["detail"] == "fun println()"


# ── Hover ──────────────────────────────────────────────────────────


class TestHoverService:
    async def test_hover(self):
        conn = _mock_conn(return_value={"contents": {"kind": "markdown", "value": "Int"}})
        svc = HoverService(conn)

        result = await svc.hover("file:///a.kt", 1, 2)

        conn.send_request.assert_called_once_with(
            "textDocument/hover",
            {
                "textDocument": {"uri": "file:///a.kt"},
                "position": {"line": 1, "character": 2},
            },
        )
        assert result is not None

    async def test_hover_returns_none(self):
        conn = _mock_conn(return_value=None)
        svc = HoverService(conn)
        assert await svc.hover("file:///a.kt", 0, 0) is None

    async def test_signature_help(self):
        conn = _mock_conn(return_value={"signatures": []})
        svc = HoverService(conn)

        result = await svc.signature_help("file:///a.kt", 3, 10)

        conn.send_request.assert_called_once_with(
            "textDocument/signatureHelp",
            {
                "textDocument": {"uri": "file:///a.kt"},
                "position": {"line": 3, "character": 10},
            },
        )


# ── Navigation ─────────────────────────────────────────────────────


class TestNavigationService:
    async def test_definition(self):
        conn = _mock_conn(return_value=[{"uri": "file:///b.kt", "range": {}}])
        svc = NavigationService(conn)
        result = await svc.definition("file:///a.kt", 5, 3)
        conn.send_request.assert_called_once_with(
            "textDocument/definition",
            {
                "textDocument": {"uri": "file:///a.kt"},
                "position": {"line": 5, "character": 3},
            },
        )
        assert isinstance(result, list)

    async def test_type_definition(self):
        conn = _mock_conn()
        svc = NavigationService(conn)
        await svc.type_definition("file:///a.kt", 1, 1)
        conn.send_request.assert_called_once()
        assert conn.send_request.call_args[0][0] == "textDocument/typeDefinition"

    async def test_declaration(self):
        conn = _mock_conn()
        svc = NavigationService(conn)
        await svc.declaration("file:///a.kt", 1, 1)
        assert conn.send_request.call_args[0][0] == "textDocument/declaration"

    async def test_implementation(self):
        conn = _mock_conn()
        svc = NavigationService(conn)
        await svc.implementation("file:///a.kt", 1, 1)
        assert conn.send_request.call_args[0][0] == "textDocument/implementation"

    async def test_references(self):
        conn = _mock_conn()
        svc = NavigationService(conn)
        await svc.references("file:///a.kt", 1, 1)
        args = conn.send_request.call_args
        assert args[0][0] == "textDocument/references"
        assert args[0][1]["context"]["includeDeclaration"] is True

    async def test_references_exclude_declaration(self):
        conn = _mock_conn()
        svc = NavigationService(conn)
        await svc.references("file:///a.kt", 1, 1, include_declaration=False)
        args = conn.send_request.call_args
        assert args[0][1]["context"]["includeDeclaration"] is False


# ── Symbols ────────────────────────────────────────────────────────


class TestSymbolService:
    async def test_document_symbols(self):
        conn = _mock_conn(return_value=[{"name": "main", "kind": 12}])
        svc = SymbolService(conn)
        result = await svc.document_symbols("file:///a.kt")
        conn.send_request.assert_called_once_with(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": "file:///a.kt"}},
        )
        assert result == [{"name": "main", "kind": 12}]

    async def test_workspace_symbols(self):
        conn = _mock_conn(return_value=[])
        svc = SymbolService(conn)
        await svc.workspace_symbols("MyClass")
        conn.send_request.assert_called_once_with("workspace/symbol", {"query": "MyClass"})


# ── Formatting ─────────────────────────────────────────────────────


class TestFormattingService:
    async def test_format_defaults(self):
        conn = _mock_conn(return_value=[])
        svc = FormattingService(conn)
        await svc.format("file:///a.kt")
        args = conn.send_request.call_args[0]
        assert args[0] == "textDocument/formatting"
        assert args[1]["options"]["tabSize"] == 4
        assert args[1]["options"]["insertSpaces"] is True

    async def test_format_custom_options(self):
        conn = _mock_conn(return_value=[])
        svc = FormattingService(conn)
        await svc.format("file:///a.kt", tab_size=2, insert_spaces=False)
        args = conn.send_request.call_args[0]
        assert args[1]["options"]["tabSize"] == 2
        assert args[1]["options"]["insertSpaces"] is False

    async def test_format_range(self):
        conn = _mock_conn(return_value=[])
        svc = FormattingService(conn)
        await svc.format_range("file:///a.kt", 0, 0, 10, 0)
        args = conn.send_request.call_args[0]
        assert args[0] == "textDocument/rangeFormatting"
        assert args[1]["range"]["start"] == {"line": 0, "character": 0}
        assert args[1]["range"]["end"] == {"line": 10, "character": 0}


# ── Code Actions ───────────────────────────────────────────────────


class TestCodeActionService:
    async def test_get_actions(self):
        conn = _mock_conn(return_value=[])
        svc = CodeActionService(conn)
        await svc.get_actions("file:///a.kt", 0, 0, 5, 0)
        args = conn.send_request.call_args[0]
        assert args[0] == "textDocument/codeAction"
        assert args[1]["context"]["diagnostics"] == []

    async def test_get_actions_with_filter(self):
        conn = _mock_conn(return_value=[])
        svc = CodeActionService(conn)
        await svc.get_actions("file:///a.kt", 0, 0, 5, 0, only=["quickfix"])
        args = conn.send_request.call_args[0]
        assert args[1]["context"]["only"] == ["quickfix"]

    async def test_get_actions_with_diagnostics(self):
        diags = [{"message": "err", "severity": 1}]
        conn = _mock_conn(return_value=[])
        svc = CodeActionService(conn)
        await svc.get_actions("file:///a.kt", 0, 0, 5, 0, diagnostics=diags)
        args = conn.send_request.call_args[0]
        assert args[1]["context"]["diagnostics"] == diags

    async def test_resolve(self):
        action = {"title": "Fix"}
        conn = _mock_conn(return_value={**action, "edit": {}})
        svc = CodeActionService(conn)
        result = await svc.resolve(action)
        conn.send_request.assert_called_once_with("codeAction/resolve", action)

    async def test_code_lens(self):
        conn = _mock_conn(return_value=[])
        svc = CodeActionService(conn)
        await svc.code_lens("file:///a.kt")
        conn.send_request.assert_called_once_with(
            "textDocument/codeLens", {"textDocument": {"uri": "file:///a.kt"}}
        )

    async def test_code_lens_resolve(self):
        lens = {"range": {}, "command": None}
        conn = _mock_conn()
        svc = CodeActionService(conn)
        await svc.code_lens_resolve(lens)
        conn.send_request.assert_called_once_with("codeLens/resolve", lens)


# ── Hierarchy ──────────────────────────────────────────────────────


class TestHierarchyService:
    async def test_prepare_call_hierarchy(self):
        conn = _mock_conn(return_value=[{"name": "foo"}])
        svc = HierarchyService(conn)
        result = await svc.prepare_call_hierarchy("file:///a.kt", 1, 2)
        conn.send_request.assert_called_once_with(
            "textDocument/prepareCallHierarchy",
            {
                "textDocument": {"uri": "file:///a.kt"},
                "position": {"line": 1, "character": 2},
            },
        )

    async def test_incoming_calls(self):
        conn = _mock_conn()
        # First call: prepareCallHierarchy returns items
        # Second call: incomingCalls returns results
        conn.send_request.side_effect = [
            [{"name": "foo", "uri": "file:///a.kt"}],
            [{"from": {"name": "bar"}}],
        ]
        svc = HierarchyService(conn)
        result = await svc.incoming_calls("file:///a.kt", 1, 2)

        assert conn.send_request.call_count == 2
        second_call = conn.send_request.call_args_list[1]
        assert second_call[0][0] == "callHierarchy/incomingCalls"
        assert second_call[0][1]["item"]["name"] == "foo"

    async def test_incoming_calls_no_items(self):
        conn = _mock_conn(return_value=None)
        svc = HierarchyService(conn)
        result = await svc.incoming_calls("file:///a.kt", 1, 2)
        assert result is None
        assert conn.send_request.call_count == 1

    async def test_outgoing_calls(self):
        conn = _mock_conn()
        conn.send_request.side_effect = [
            [{"name": "foo"}],
            [{"to": {"name": "baz"}}],
        ]
        svc = HierarchyService(conn)
        result = await svc.outgoing_calls("file:///a.kt", 1, 2)

        second_call = conn.send_request.call_args_list[1]
        assert second_call[0][0] == "callHierarchy/outgoingCalls"

    async def test_prepare_type_hierarchy(self):
        conn = _mock_conn(return_value=[{"name": "MyClass"}])
        svc = HierarchyService(conn)
        await svc.prepare_type_hierarchy("file:///a.kt", 3, 4)
        assert conn.send_request.call_args[0][0] == "textDocument/prepareTypeHierarchy"

    async def test_supertypes(self):
        conn = _mock_conn()
        conn.send_request.side_effect = [
            [{"name": "Child"}],
            [{"name": "Parent"}],
        ]
        svc = HierarchyService(conn)
        result = await svc.supertypes("file:///a.kt", 1, 2)
        assert conn.send_request.call_args_list[1][0][0] == "typeHierarchy/supertypes"

    async def test_subtypes(self):
        conn = _mock_conn()
        conn.send_request.side_effect = [
            [{"name": "Parent"}],
            [{"name": "Child"}],
        ]
        svc = HierarchyService(conn)
        result = await svc.subtypes("file:///a.kt", 1, 2)
        assert conn.send_request.call_args_list[1][0][0] == "typeHierarchy/subtypes"

    async def test_supertypes_no_items(self):
        conn = _mock_conn(return_value=None)
        svc = HierarchyService(conn)
        assert await svc.supertypes("file:///a.kt", 1, 2) is None


# ── Refactoring ────────────────────────────────────────────────────


class TestRefactoringService:
    async def test_rename(self):
        conn = _mock_conn(return_value={"changes": {}})
        svc = RefactoringService(conn)
        result = await svc.rename("file:///a.kt", 5, 3, "newName")
        args = conn.send_request.call_args[0]
        assert args[0] == "textDocument/rename"
        assert args[1]["newName"] == "newName"
        assert args[1]["position"] == {"line": 5, "character": 3}

    async def test_prepare_rename(self):
        conn = _mock_conn(return_value={"range": {}, "placeholder": "oldName"})
        svc = RefactoringService(conn)
        result = await svc.prepare_rename("file:///a.kt", 5, 3)
        assert conn.send_request.call_args[0][0] == "textDocument/prepareRename"
        assert result["placeholder"] == "oldName"


# ── Kotlin Extensions ─────────────────────────────────────────────


class TestKotlinExtensionService:
    async def test_jar_class_contents(self):
        conn = _mock_conn(return_value="class Foo {}")
        svc = KotlinExtensionService(conn)
        result = await svc.jar_class_contents("file:///lib.jar!/Foo.class")
        conn.send_request.assert_called_once_with(
            "kotlin/jarClassContents",
            {"uri": "file:///lib.jar!/Foo.class"},
        )
        assert result == "class Foo {}"

    async def test_build_output_location(self):
        conn = _mock_conn(return_value="/project/build/classes")
        svc = KotlinExtensionService(conn)
        result = await svc.build_output_location()
        conn.send_request.assert_called_once_with("kotlin/buildOutputLocation", {})

    async def test_main_class(self):
        conn = _mock_conn(return_value={"uri": "file:///a.kt", "className": "MainKt"})
        svc = KotlinExtensionService(conn)
        result = await svc.main_class("file:///a.kt")
        conn.send_request.assert_called_once_with("kotlin/mainClass", {"uri": "file:///a.kt"})

    async def test_override_member(self):
        conn = _mock_conn(return_value=[{"label": "toString()"}])
        svc = KotlinExtensionService(conn)
        result = await svc.override_member("file:///a.kt", 5, 0)
        args = conn.send_request.call_args[0]
        assert args[0] == "kotlin/overrideMember"
        assert args[1]["position"] == {"line": 5, "character": 0}


# ── Diagnostics ────────────────────────────────────────────────────


class TestDiagnosticsService:
    def test_subscribes_on_init(self):
        conn = _mock_conn()
        svc = DiagnosticsService(conn)
        conn.on_notification.assert_called_once_with(
            "textDocument/publishDiagnostics", svc._on_diagnostics
        )

    def test_get_empty(self):
        conn = _mock_conn()
        svc = DiagnosticsService(conn)
        assert svc.get() == {}
        assert svc.get("file:///a.kt") == {"file:///a.kt": []}

    def test_caches_diagnostics(self):
        conn = _mock_conn()
        svc = DiagnosticsService(conn)

        svc._on_diagnostics({
            "uri": "file:///a.kt",
            "diagnostics": [{"message": "err", "severity": 1}],
        })

        result = svc.get("file:///a.kt")
        assert len(result["file:///a.kt"]) == 1
        assert result["file:///a.kt"][0]["message"] == "err"

    def test_get_all(self):
        conn = _mock_conn()
        svc = DiagnosticsService(conn)

        svc._on_diagnostics({"uri": "file:///a.kt", "diagnostics": [{"severity": 1}]})
        svc._on_diagnostics({"uri": "file:///b.kt", "diagnostics": [{"severity": 2}]})

        all_diags = svc.get()
        assert "file:///a.kt" in all_diags
        assert "file:///b.kt" in all_diags

    def test_get_errors(self):
        conn = _mock_conn()
        svc = DiagnosticsService(conn)

        svc._on_diagnostics({
            "uri": "file:///a.kt",
            "diagnostics": [
                {"message": "error", "severity": 1},
                {"message": "warning", "severity": 2},
            ],
        })

        errors = svc.get_errors("file:///a.kt")
        assert len(errors["file:///a.kt"]) == 1
        assert errors["file:///a.kt"][0]["message"] == "error"

    def test_get_warnings(self):
        conn = _mock_conn()
        svc = DiagnosticsService(conn)

        svc._on_diagnostics({
            "uri": "file:///a.kt",
            "diagnostics": [
                {"message": "error", "severity": 1},
                {"message": "warning", "severity": 2},
            ],
        })

        warnings = svc.get_warnings("file:///a.kt")
        assert len(warnings["file:///a.kt"]) == 1
        assert warnings["file:///a.kt"][0]["message"] == "warning"

    def test_get_errors_no_errors(self):
        conn = _mock_conn()
        svc = DiagnosticsService(conn)

        svc._on_diagnostics({
            "uri": "file:///a.kt",
            "diagnostics": [{"message": "warn", "severity": 2}],
        })

        errors = svc.get_errors("file:///a.kt")
        assert errors == {}

    def test_clear(self):
        conn = _mock_conn()
        svc = DiagnosticsService(conn)

        svc._on_diagnostics({"uri": "file:///a.kt", "diagnostics": [{"severity": 1}]})
        svc.clear()

        assert svc.get() == {}

    def test_on_update_handler(self):
        conn = _mock_conn()
        svc = DiagnosticsService(conn)

        received = []
        svc.on_update(lambda uri, diags: received.append((uri, diags)))

        svc._on_diagnostics({"uri": "file:///a.kt", "diagnostics": [{"severity": 1}]})

        assert len(received) == 1
        assert received[0][0] == "file:///a.kt"

    def test_replaces_diagnostics_for_uri(self):
        conn = _mock_conn()
        svc = DiagnosticsService(conn)

        svc._on_diagnostics({"uri": "file:///a.kt", "diagnostics": [{"severity": 1}, {"severity": 2}]})
        svc._on_diagnostics({"uri": "file:///a.kt", "diagnostics": []})

        assert svc.get("file:///a.kt") == {"file:///a.kt": []}
