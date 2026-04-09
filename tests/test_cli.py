from __future__ import annotations

import json
from argparse import Namespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kotlineer.cli import (
    _print_locations,
    _print_symbols,
    _resolve_files,
    _uri_to_path,
    apply_text_edits,
    build_parser,
    cmd_check,
    cmd_definition,
    cmd_format,
    cmd_hover,
    cmd_references,
    cmd_symbols,
    find_kotlin_files,
)

# ── Helpers ─────────────────────────────────────────────────────────


class TestUriToPath:
    def test_simple(self):
        assert _uri_to_path("file:///src/Main.kt") == "/src/Main.kt"

    def test_encoded_spaces(self):
        assert _uri_to_path("file:///my%20project/Main.kt") == "/my project/Main.kt"

    def test_no_scheme(self):
        assert _uri_to_path("/plain/path") == "/plain/path"


class TestFindKotlinFiles:
    def test_finds_kt_files(self, tmp_path):
        (tmp_path / "Main.kt").touch()
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "Util.kt").touch()
        (tmp_path / "readme.md").touch()

        result = find_kotlin_files(tmp_path)
        names = [p.name for p in result]
        assert "Main.kt" in names
        assert "Util.kt" in names
        assert "readme.md" not in names

    def test_ignores_build_dirs(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "App.kt").touch()
        (tmp_path / "build").mkdir()
        (tmp_path / "build" / "Generated.kt").touch()
        (tmp_path / ".gradle").mkdir()
        (tmp_path / ".gradle" / "Cache.kt").touch()
        (tmp_path / ".idea").mkdir()
        (tmp_path / ".idea" / "Idea.kt").touch()

        result = find_kotlin_files(tmp_path)
        names = [p.name for p in result]
        assert "App.kt" in names
        assert "Generated.kt" not in names
        assert "Cache.kt" not in names
        assert "Idea.kt" not in names

    def test_empty_workspace(self, tmp_path):
        assert find_kotlin_files(tmp_path) == []

    def test_sorted_output(self, tmp_path):
        (tmp_path / "b.kt").touch()
        (tmp_path / "a.kt").touch()
        result = find_kotlin_files(tmp_path)
        assert result[0].name == "a.kt"
        assert result[1].name == "b.kt"


class TestApplyTextEdits:
    def test_single_replace(self):
        text = "hello world"
        edits = [
            {
                "range": {
                    "start": {"line": 0, "character": 6},
                    "end": {"line": 0, "character": 11},
                },
                "newText": "kotlin",
            }
        ]
        assert apply_text_edits(text, edits) == "hello kotlin"

    def test_insert(self):
        text = "fun main() {}"
        edits = [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 0},
                },
                "newText": "// entry\n",
            }
        ]
        assert apply_text_edits(text, edits) == "// entry\nfun main() {}"

    def test_multiline_replace(self):
        text = "line1\nline2\nline3"
        edits = [
            {
                "range": {
                    "start": {"line": 0, "character": 5},
                    "end": {"line": 2, "character": 0},
                },
                "newText": "\nnew\n",
            }
        ]
        assert apply_text_edits(text, edits) == "line1\nnew\nline3"

    def test_multiple_edits_reverse_order(self):
        text = "aaa bbb ccc"
        edits = [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 3},
                },
                "newText": "AAA",
            },
            {
                "range": {
                    "start": {"line": 0, "character": 8},
                    "end": {"line": 0, "character": 11},
                },
                "newText": "CCC",
            },
        ]
        assert apply_text_edits(text, edits) == "AAA bbb CCC"

    def test_delete(self):
        text = "keep remove keep"
        edits = [
            {
                "range": {
                    "start": {"line": 0, "character": 4},
                    "end": {"line": 0, "character": 11},
                },
                "newText": "",
            }
        ]
        assert apply_text_edits(text, edits) == "keep keep"

    def test_empty_edits(self):
        text = "unchanged"
        assert apply_text_edits(text, []) == "unchanged"


class TestResolveFiles:
    def test_explicit_files(self, tmp_path):
        f = tmp_path / "Main.kt"
        f.touch()
        args = Namespace(files=[str(f)], workspace=str(tmp_path))
        result = _resolve_files(args)
        assert len(result) == 1
        assert result[0] == f.resolve()

    def test_relative_files(self, tmp_path):
        (tmp_path / "src").mkdir()
        f = tmp_path / "src" / "Main.kt"
        f.touch()
        args = Namespace(files=["src/Main.kt"], workspace=str(tmp_path))
        result = _resolve_files(args)
        assert len(result) == 1
        assert result[0] == f.resolve()

    def test_no_files_discovers(self, tmp_path):
        (tmp_path / "App.kt").touch()
        args = Namespace(files=[], workspace=str(tmp_path))
        result = _resolve_files(args)
        assert len(result) == 1
        assert result[0].name == "App.kt"


# ── Parser ──────────────────────────────────────────────────────────


class TestBuildParser:
    def test_check_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["check"])
        assert args.command == "check"
        assert args.files == []
        assert args.errors_only is False
        assert args.settle_time == 3.0

    def test_check_with_options(self):
        parser = build_parser()
        args = parser.parse_args(["check", "a.kt", "b.kt", "--errors-only", "--settle-time", "5"])
        assert args.files == ["a.kt", "b.kt"]
        assert args.errors_only is True
        assert args.settle_time == 5.0

    def test_format_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["format"])
        assert args.command == "format"
        assert args.check is False
        assert args.diff is False

    def test_format_check_mode(self):
        parser = build_parser()
        args = parser.parse_args(["format", "--check"])
        assert args.check is True

    def test_format_diff_mode(self):
        parser = build_parser()
        args = parser.parse_args(["format", "--diff"])
        assert args.diff is True

    def test_hover_args(self):
        parser = build_parser()
        args = parser.parse_args(["hover", "Main.kt", "10", "5"])
        assert args.file == "Main.kt"
        assert args.line == 10
        assert args.col == 5

    def test_definition_args(self):
        parser = build_parser()
        args = parser.parse_args(["definition", "Main.kt", "3", "12"])
        assert args.file == "Main.kt"
        assert args.line == 3
        assert args.col == 12

    def test_references_args(self):
        parser = build_parser()
        args = parser.parse_args(["references", "Main.kt", "7", "1"])
        assert args.line == 7
        assert args.col == 1

    def test_symbols_file(self):
        parser = build_parser()
        args = parser.parse_args(["symbols", "Main.kt"])
        assert args.file == "Main.kt"
        assert args.query is None

    def test_symbols_query(self):
        parser = build_parser()
        args = parser.parse_args(["symbols", "--query", "MyClass"])
        assert args.file is None
        assert args.query == "MyClass"

    def test_global_options(self):
        parser = build_parser()
        args = parser.parse_args(
            ["--server-path", "/usr/bin/kls", "-w", "/proj", "--timeout", "60", "--json", "check"]
        )
        assert args.server_path == "/usr/bin/kls"
        assert args.workspace == "/proj"
        assert args.timeout == 60.0
        assert args.json is True

    def test_connect_option(self):
        parser = build_parser()
        args = parser.parse_args(["--connect", "10.0.0.1:9999", "check"])
        assert args.connect == "10.0.0.1:9999"

    def test_connect_default_is_none(self):
        parser = build_parser()
        args = parser.parse_args(["check"])
        assert args.connect is None

    def test_no_subcommand_raises(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])


# ── Print helpers ───────────────────────────────────────────────────


class TestPrintLocations:
    def test_no_results(self, capsys):
        code = _print_locations(None, as_json=False)
        assert code == 0
        assert "No results" in capsys.readouterr().err

    def test_empty_list(self, capsys):
        code = _print_locations([], as_json=False)
        assert code == 0

    def test_single_location(self, capsys):
        loc = {
            "uri": "file:///src/Main.kt",
            "range": {"start": {"line": 9, "character": 4}, "end": {"line": 9, "character": 10}},
        }
        code = _print_locations(loc, as_json=False)
        assert code == 0
        out = capsys.readouterr().out
        assert "/src/Main.kt:10:5" in out

    def test_multiple_locations(self, capsys):
        locs = [
            {
                "uri": "file:///a.kt",
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 1}},
            },
            {
                "uri": "file:///b.kt",
                "range": {"start": {"line": 4, "character": 2}, "end": {"line": 4, "character": 5}},
            },
        ]
        code = _print_locations(locs, as_json=False)
        assert code == 0
        out = capsys.readouterr().out
        assert "/a.kt:1:1" in out
        assert "/b.kt:5:3" in out

    def test_json_output(self, capsys):
        loc = {
            "uri": "file:///x.kt",
            "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
        }
        _print_locations([loc], as_json=True)
        parsed = json.loads(capsys.readouterr().out)
        assert len(parsed) == 1
        assert parsed[0]["uri"] == "file:///x.kt"


class TestPrintSymbols:
    def test_document_symbols(self, capsys):
        symbols = [
            {
                "name": "MyClass",
                "kind": 5,
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 10, "character": 0},
                },
                "children": [
                    {
                        "name": "myMethod",
                        "kind": 6,
                        "range": {
                            "start": {"line": 2, "character": 4},
                            "end": {"line": 5, "character": 4},
                        },
                        "children": [],
                    }
                ],
            }
        ]
        _print_symbols(symbols, indent=0)
        out = capsys.readouterr().out
        assert "Class MyClass" in out
        assert "Method myMethod" in out

    def test_workspace_symbols_with_location(self, capsys):
        symbols = [
            {
                "name": "greet",
                "kind": 12,
                "location": {
                    "uri": "file:///a.kt",
                    "range": {
                        "start": {"line": 5, "character": 0},
                        "end": {"line": 5, "character": 10},
                    },
                },
            }
        ]
        _print_symbols(symbols, indent=0)
        out = capsys.readouterr().out
        assert "Function greet" in out
        assert "line 6" in out


# ── Subcommand integration (mocked client) ──────────────────────────


def _make_args(**kwargs) -> Namespace:
    defaults = {
        "server_path": "/bin/kls",
        "workspace": "/tmp/proj",
        "timeout": 30.0,
        "json": False,
        "verbose": False,
    }
    defaults.update(kwargs)
    return Namespace(**defaults)


def _mock_client():
    client = AsyncMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.open_file = AsyncMock(return_value="file:///tmp/proj/Main.kt")
    client.capabilities = {}
    client.diagnostics = MagicMock()
    client.diagnostics.on_update = MagicMock()
    client.diagnostics.pull = AsyncMock()
    client.formatting = AsyncMock()
    client.hover = AsyncMock()
    client.navigation = AsyncMock()
    client.symbols = AsyncMock()
    return client


class TestCmdCheck:
    async def test_no_files(self, tmp_path, capsys):
        args = _make_args(files=[], workspace=str(tmp_path), errors_only=False, settle_time=0.1)
        code = await cmd_check(args)
        assert code == 0
        assert "No .kt files" in capsys.readouterr().err

    async def test_clean_diagnostics(self, tmp_path, capsys):
        kt = tmp_path / "App.kt"
        kt.write_text("fun main() {}", encoding="utf-8")

        client = _mock_client()
        client.diagnostics.get.return_value = {"file:///App.kt": []}

        args = _make_args(
            files=[str(kt)],
            workspace=str(tmp_path),
            errors_only=False,
            settle_time=0.1,
        )

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("kotlineer.cli._wait_for_diagnostics", new_callable=AsyncMock):
                code = await cmd_check(args)

        assert code == 0

    async def test_diagnostics_found(self, tmp_path, capsys):
        kt = tmp_path / "Bad.kt"
        kt.write_text("bad code", encoding="utf-8")

        diags = {
            "file:///Bad.kt": [
                {
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 3},
                    },
                    "severity": 1,
                    "message": "Unresolved reference",
                }
            ]
        }

        client = _mock_client()
        client.diagnostics.get.return_value = diags

        args = _make_args(
            files=[str(kt)],
            workspace=str(tmp_path),
            errors_only=False,
            settle_time=0.1,
        )

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("kotlineer.cli._wait_for_diagnostics", new_callable=AsyncMock):
                code = await cmd_check(args)

        assert code == 1
        out = capsys.readouterr().out
        assert "error" in out
        assert "Unresolved reference" in out

    async def test_json_output(self, tmp_path, capsys):
        kt = tmp_path / "Bad.kt"
        kt.write_text("bad", encoding="utf-8")

        diags = {
            "file:///Bad.kt": [
                {
                    "range": {
                        "start": {"line": 2, "character": 5},
                        "end": {"line": 2, "character": 8},
                    },
                    "severity": 2,
                    "message": "Unused variable",
                }
            ]
        }

        client = _mock_client()
        client.diagnostics.get.return_value = diags

        args = _make_args(
            files=[str(kt)],
            workspace=str(tmp_path),
            errors_only=False,
            settle_time=0.1,
            json=True,
        )

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("kotlineer.cli._wait_for_diagnostics", new_callable=AsyncMock):
                code = await cmd_check(args)

        assert code == 1
        parsed = json.loads(capsys.readouterr().out)
        assert "/Bad.kt" in list(parsed.keys())[0]
        assert parsed[list(parsed.keys())[0]][0]["severity"] == "warning"
        assert parsed[list(parsed.keys())[0]][0]["line"] == 3
        assert parsed[list(parsed.keys())[0]][0]["col"] == 6

    async def test_errors_only(self, tmp_path, capsys):
        kt = tmp_path / "Mix.kt"
        kt.write_text("code", encoding="utf-8")

        client = _mock_client()
        client.diagnostics.get_errors.return_value = {}

        args = _make_args(
            files=[str(kt)],
            workspace=str(tmp_path),
            errors_only=True,
            settle_time=0.1,
        )

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("kotlineer.cli._wait_for_diagnostics", new_callable=AsyncMock):
                code = await cmd_check(args)

        assert code == 0
        client.diagnostics.get_errors.assert_called_once()


class TestCmdFormat:
    async def test_no_files(self, tmp_path, capsys):
        args = _make_args(files=[], workspace=str(tmp_path), check=False, diff=False)
        code = await cmd_format(args)
        assert code == 0

    async def test_no_edits(self, tmp_path):
        kt = tmp_path / "Clean.kt"
        kt.write_text("fun main() {}", encoding="utf-8")

        client = _mock_client()
        client.formatting.format = AsyncMock(return_value=None)

        args = _make_args(files=[str(kt)], workspace=str(tmp_path), check=False, diff=False)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_format(args)

        assert code == 0

    async def test_format_writes_file(self, tmp_path, capsys):
        kt = tmp_path / "Messy.kt"
        kt.write_text("fun  main() {}", encoding="utf-8")

        edits = [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 14},
                },
                "newText": "fun main() {}",
            }
        ]

        client = _mock_client()
        client.formatting.format = AsyncMock(return_value=edits)

        args = _make_args(files=[str(kt)], workspace=str(tmp_path), check=False, diff=False)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_format(args)

        assert code == 0
        assert kt.read_text() == "fun main() {}"
        assert "Formatted" in capsys.readouterr().out

    async def test_format_check_mode(self, tmp_path, capsys):
        kt = tmp_path / "Messy.kt"
        kt.write_text("fun  main() {}", encoding="utf-8")

        edits = [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 14},
                },
                "newText": "fun main() {}",
            }
        ]

        client = _mock_client()
        client.formatting.format = AsyncMock(return_value=edits)

        args = _make_args(files=[str(kt)], workspace=str(tmp_path), check=True, diff=False)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_format(args)

        assert code == 1
        assert kt.read_text() == "fun  main() {}"  # unchanged
        assert "Would reformat" in capsys.readouterr().out

    async def test_format_diff_mode(self, tmp_path, capsys):
        kt = tmp_path / "Messy.kt"
        kt.write_text("fun  main() {}", encoding="utf-8")

        edits = [
            {
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 14},
                },
                "newText": "fun main() {}",
            }
        ]

        client = _mock_client()
        client.formatting.format = AsyncMock(return_value=edits)

        args = _make_args(files=[str(kt)], workspace=str(tmp_path), check=False, diff=True)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_format(args)

        assert code == 0
        out = capsys.readouterr().out
        assert "---" in out or "+++" in out


class TestCmdHover:
    async def test_no_hover(self, tmp_path, capsys):
        client = _mock_client()
        client.hover.hover = AsyncMock(return_value=None)

        args = _make_args(file=str(tmp_path / "A.kt"), line=1, col=1)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_hover(args)

        assert code == 0
        assert "No hover info" in capsys.readouterr().err

    async def test_hover_markup(self, tmp_path, capsys):
        client = _mock_client()
        client.hover.hover = AsyncMock(
            return_value={"contents": {"kind": "markdown", "value": "fun main(): Unit"}}
        )

        args = _make_args(file=str(tmp_path / "A.kt"), line=5, col=3)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_hover(args)

        assert code == 0
        assert "fun main(): Unit" in capsys.readouterr().out
        client.hover.hover.assert_called_with("file:///tmp/proj/Main.kt", 4, 2)

    async def test_hover_string_contents(self, tmp_path, capsys):
        client = _mock_client()
        client.hover.hover = AsyncMock(return_value={"contents": "just a string"})

        args = _make_args(file=str(tmp_path / "A.kt"), line=1, col=1)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_hover(args)

        assert code == 0
        assert "just a string" in capsys.readouterr().out

    async def test_hover_json(self, tmp_path, capsys):
        hover_result = {"contents": {"value": "Int"}}
        client = _mock_client()
        client.hover.hover = AsyncMock(return_value=hover_result)

        args = _make_args(file=str(tmp_path / "A.kt"), line=1, col=1, json=True)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_hover(args)

        assert code == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed["contents"]["value"] == "Int"


class TestCmdDefinition:
    async def test_definition(self, tmp_path, capsys):
        loc = {
            "uri": "file:///src/Service.kt",
            "range": {"start": {"line": 10, "character": 4}, "end": {"line": 10, "character": 15}},
        }
        client = _mock_client()
        client.navigation.definition = AsyncMock(return_value=loc)

        args = _make_args(file=str(tmp_path / "A.kt"), line=5, col=10)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_definition(args)

        assert code == 0
        assert "/src/Service.kt:11:5" in capsys.readouterr().out
        client.navigation.definition.assert_called_with("file:///tmp/proj/Main.kt", 4, 9)

    async def test_definition_no_result(self, tmp_path, capsys):
        client = _mock_client()
        client.navigation.definition = AsyncMock(return_value=None)

        args = _make_args(file=str(tmp_path / "A.kt"), line=1, col=1)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_definition(args)

        assert code == 0
        assert "No results" in capsys.readouterr().err


class TestCmdReferences:
    async def test_references(self, tmp_path, capsys):
        locs = [
            {
                "uri": "file:///a.kt",
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 5}},
            },
            {
                "uri": "file:///b.kt",
                "range": {
                    "start": {"line": 3, "character": 8},
                    "end": {"line": 3, "character": 13},
                },
            },
        ]
        client = _mock_client()
        client.navigation.references = AsyncMock(return_value=locs)

        args = _make_args(file=str(tmp_path / "A.kt"), line=2, col=4)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_references(args)

        assert code == 0
        out = capsys.readouterr().out
        assert "/a.kt:1:1" in out
        assert "/b.kt:4:9" in out


class TestCmdSymbols:
    async def test_document_symbols(self, tmp_path, capsys):
        syms = [
            {
                "name": "App",
                "kind": 5,
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 10, "character": 0},
                },
                "children": [],
            }
        ]
        client = _mock_client()
        client.symbols.document_symbols = AsyncMock(return_value=syms)

        args = _make_args(file=str(tmp_path / "App.kt"), query=None)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_symbols(args)

        assert code == 0
        assert "Class App" in capsys.readouterr().out

    async def test_workspace_symbols(self, tmp_path, capsys):
        syms = [
            {
                "name": "UserService",
                "kind": 5,
                "location": {
                    "uri": "file:///src/UserService.kt",
                    "range": {
                        "start": {"line": 2, "character": 0},
                        "end": {"line": 20, "character": 0},
                    },
                },
            }
        ]
        client = _mock_client()
        client.symbols.workspace_symbols = AsyncMock(return_value=syms)

        args = _make_args(file=None, query="UserService")

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_symbols(args)

        assert code == 0
        out = capsys.readouterr().out
        assert "Class UserService" in out

    async def test_no_symbols(self, tmp_path, capsys):
        client = _mock_client()
        client.symbols.document_symbols = AsyncMock(return_value=[])

        args = _make_args(file=str(tmp_path / "Empty.kt"), query=None)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_symbols(args)

        assert code == 0
        assert "No symbols" in capsys.readouterr().err

    async def test_symbols_json(self, tmp_path, capsys):
        syms = [
            {
                "name": "Foo",
                "kind": 5,
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
                "children": [],
            }
        ]
        client = _mock_client()
        client.symbols.document_symbols = AsyncMock(return_value=syms)

        args = _make_args(file=str(tmp_path / "Foo.kt"), query=None, json=True)

        with patch("kotlineer.cli._open_client") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=client)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            code = await cmd_symbols(args)

        assert code == 0
        parsed = json.loads(capsys.readouterr().out)
        assert parsed[0]["name"] == "Foo"
