from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from . import __version__
from .client import KotlinLspClient

logger = logging.getLogger(__name__)

IGNORE_DIRS = {"build", ".gradle", ".idea", "out", ".git"}

SEVERITY_LABELS = {1: "error", 2: "warning", 3: "info", 4: "hint"}


# ── Helpers ─────────────────────────────────────────────────────────


def _uri_to_path(uri: str) -> str:
    parsed = urlparse(uri)
    return unquote(parsed.path)


def find_kotlin_files(workspace: Path) -> list[Path]:
    return sorted(
        p
        for p in workspace.rglob("*.kt")
        if not any(part in IGNORE_DIRS for part in p.parts)
    )


def apply_text_edits(text: str, edits: list[dict[str, Any]]) -> str:
    lines = text.split("\n")

    sorted_edits = sorted(
        edits,
        key=lambda e: (
            e["range"]["start"]["line"],
            e["range"]["start"]["character"],
        ),
        reverse=True,
    )

    for edit in sorted_edits:
        start = edit["range"]["start"]
        end = edit["range"]["end"]
        new_text = edit["newText"]

        sl, sc = start["line"], start["character"]
        el, ec = end["line"], end["character"]

        before = lines[sl][:sc]
        after = lines[el][ec:]

        new_lines = (before + new_text + after).split("\n")
        lines[sl : el + 1] = new_lines

    return "\n".join(lines)


@asynccontextmanager
async def _open_client(args: argparse.Namespace):
    workspace = str(Path(args.workspace).resolve())
    if args.connect:
        host, port_str = args.connect.rsplit(":", 1)
        client = KotlinLspClient(
            workspace,
            host=host,
            port=int(port_str),
            request_timeout=args.timeout,
        )
    else:
        client = KotlinLspClient.spawn(
            workspace,
            server_path=args.server_path,
            request_timeout=args.timeout,
        )
    try:
        await client.start()
        yield client
    finally:
        await client.stop()


def _resolve_files(args: argparse.Namespace) -> list[Path]:
    if args.files:
        workspace = Path(args.workspace).resolve()
        result = []
        for f in args.files:
            p = Path(f)
            if not p.is_absolute():
                p = workspace / p
            result.append(p.resolve())
        return result
    return find_kotlin_files(Path(args.workspace).resolve())


async def _wait_for_diagnostics(
    client: KotlinLspClient,
    timeout: float = 30.0,
    settle: float = 3.0,
) -> None:
    loop = asyncio.get_event_loop()
    last_update: float | None = None  # None until first diagnostic arrives

    def on_diag(_uri: str, _diags: list) -> None:
        nonlocal last_update
        last_update = loop.time()

    client.diagnostics.on_update(on_diag)

    deadline = loop.time() + timeout
    while True:
        now = loop.time()
        if now > deadline:
            break
        # Only apply settle logic after at least one diagnostic arrived
        if last_update is not None and now - last_update >= settle:
            break
        await asyncio.sleep(0.5)


# ── Subcommands ─────────────────────────────────────────────────────


async def cmd_check(args: argparse.Namespace) -> int:
    files = _resolve_files(args)
    if not files:
        print("No .kt files found.", file=sys.stderr)
        return 0

    async with _open_client(args) as client:
        # Ensure DiagnosticsService (and its notification handler) is
        # created before opening files so that no server-pushed
        # diagnostics are lost.
        _ = client.diagnostics

        uris: list[str] = []
        for f in files:
            uris.append(await client.open_file(str(f)))

        # Use pull model if the server advertises diagnosticProvider,
        # otherwise fall back to waiting for pushed notifications.
        caps = client.capabilities or {}
        if caps.get("diagnosticProvider"):
            for uri in uris:
                await client.diagnostics.pull(uri)
        else:
            await _wait_for_diagnostics(
                client,
                timeout=args.timeout,
                settle=args.settle_time,
            )

        all_diags = (
            client.diagnostics.get_errors()
            if args.errors_only
            else client.diagnostics.get()
        )

    if args.json:
        output: dict[str, Any] = {}
        for uri, diags in all_diags.items():
            if not diags:
                continue
            path = _uri_to_path(uri)
            output[path] = [
                {
                    "line": d["range"]["start"]["line"] + 1,
                    "col": d["range"]["start"]["character"] + 1,
                    "severity": SEVERITY_LABELS.get(d.get("severity", 1), "error"),
                    "message": d.get("message", ""),
                }
                for d in diags
            ]
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        for uri, diags in all_diags.items():
            if not diags:
                continue
            path = _uri_to_path(uri)
            for d in diags:
                line = d["range"]["start"]["line"] + 1
                col = d["range"]["start"]["character"] + 1
                sev = SEVERITY_LABELS.get(d.get("severity", 1), "error")
                msg = d.get("message", "")
                print(f"{path}:{line}:{col}: {sev}: {msg}")

    has_issues = any(len(diags) > 0 for diags in all_diags.values())
    return 1 if has_issues else 0


async def cmd_format(args: argparse.Namespace) -> int:
    files = _resolve_files(args)
    if not files:
        print("No .kt files found.", file=sys.stderr)
        return 0

    changed = False

    async with _open_client(args) as client:
        for f in files:
            uri = await client.open_file(str(f))
            edits = await client.formatting.format(uri)

            if not edits:
                continue

            original = f.read_text(encoding="utf-8")
            formatted = apply_text_edits(original, edits)

            if original == formatted:
                continue

            changed = True

            if args.diff:
                diff = difflib.unified_diff(
                    original.splitlines(keepends=True),
                    formatted.splitlines(keepends=True),
                    fromfile=str(f),
                    tofile=str(f),
                )
                sys.stdout.writelines(diff)
            elif args.check:
                print(f"Would reformat {f}")
            else:
                f.write_text(formatted, encoding="utf-8")
                print(f"Formatted {f}")

    if args.check and changed:
        return 1
    return 0


async def cmd_hover(args: argparse.Namespace) -> int:
    async with _open_client(args) as client:
        uri = await client.open_file(args.file)
        result = await client.hover.hover(uri, args.line - 1, args.col - 1)

    if not result:
        print("No hover info.", file=sys.stderr)
        return 0

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        contents = result.get("contents", {})
        if isinstance(contents, dict):
            print(contents.get("value", ""))
        elif isinstance(contents, str):
            print(contents)
        elif isinstance(contents, list):
            for item in contents:
                print(item.get("value", item) if isinstance(item, dict) else item)

    return 0


async def cmd_definition(args: argparse.Namespace) -> int:
    async with _open_client(args) as client:
        uri = await client.open_file(args.file)
        result = await client.navigation.definition(uri, args.line - 1, args.col - 1)

    return _print_locations(result, args.json)


async def cmd_references(args: argparse.Namespace) -> int:
    async with _open_client(args) as client:
        uri = await client.open_file(args.file)
        result = await client.navigation.references(uri, args.line - 1, args.col - 1)

    return _print_locations(result, args.json)


def _print_locations(result: Any, as_json: bool) -> int:
    if not result:
        print("No results.", file=sys.stderr)
        return 0

    locations = result if isinstance(result, list) else [result]

    if as_json:
        print(json.dumps(locations, indent=2, ensure_ascii=False))
    else:
        for loc in locations:
            path = _uri_to_path(loc["uri"])
            line = loc["range"]["start"]["line"] + 1
            col = loc["range"]["start"]["character"] + 1
            print(f"{path}:{line}:{col}")

    return 0


async def cmd_symbols(args: argparse.Namespace) -> int:
    async with _open_client(args) as client:
        if args.query:
            result = await client.symbols.workspace_symbols(args.query)
        else:
            uri = await client.open_file(args.file)
            result = await client.symbols.document_symbols(uri)

    if not result:
        print("No symbols found.", file=sys.stderr)
        return 0

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_symbols(result, indent=0)

    return 0


def _print_symbols(symbols: list[dict[str, Any]], indent: int) -> None:
    kind_names = {
        1: "File", 2: "Module", 3: "Namespace", 4: "Package",
        5: "Class", 6: "Method", 7: "Property", 8: "Field",
        9: "Constructor", 10: "Enum", 11: "Interface", 12: "Function",
        13: "Variable", 14: "Constant", 15: "String", 16: "Number",
        17: "Boolean", 18: "Array", 19: "Object", 20: "Key",
        21: "Null", 22: "EnumMember", 23: "Struct", 24: "Event",
        25: "Operator", 26: "TypeParameter",
    }
    for sym in symbols:
        kind = kind_names.get(sym.get("kind", 0), "?")
        name = sym.get("name", "?")
        prefix = "  " * indent

        if "location" in sym:
            loc = sym["location"]
            line = loc["range"]["start"]["line"] + 1
            print(f"{prefix}{kind} {name}  (line {line})")
        else:
            line = sym.get("range", {}).get("start", {}).get("line", 0) + 1
            print(f"{prefix}{kind} {name}  (line {line})")

        children = sym.get("children", [])
        if children:
            _print_symbols(children, indent + 1)


# ── Argparse ────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kotlineer",
        description="CLI for JetBrains kotlin-lsp",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--connect",
        default=None,
        help="Connect to a running kotlin-lsp server at host:port instead of spawning a new one",
    )
    parser.add_argument(
        "--server-path",
        default=os.environ.get("KOTLINEER_SERVER", "kotlin-lsp"),
        help="Path to kotlin-lsp binary (env: KOTLINEER_SERVER)",
    )
    parser.add_argument(
        "-w", "--workspace",
        default=".",
        help="Project root directory (default: cwd)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # check
    p_check = sub.add_parser("check", help="Run diagnostics on Kotlin files")
    p_check.add_argument("files", nargs="*", help="Files to check (default: all .kt in workspace)")
    p_check.add_argument("--errors-only", action="store_true", help="Show only errors")
    p_check.add_argument(
        "--settle-time", type=float, default=3.0,
        help="Seconds to wait after last diagnostic update (default: 3)",
    )
    p_check.set_defaults(func=cmd_check)

    # format
    p_fmt = sub.add_parser("format", help="Format Kotlin files")
    p_fmt.add_argument("files", nargs="*", help="Files to format (default: all .kt in workspace)")
    p_fmt.add_argument("--check", action="store_true", dest="check", help="Dry-run: exit 1 if changes needed")
    p_fmt.add_argument("--diff", action="store_true", help="Print unified diff instead of writing")
    p_fmt.set_defaults(func=cmd_format)

    # hover
    p_hover = sub.add_parser("hover", help="Get type/docs at a position")
    p_hover.add_argument("file", help="Kotlin file path")
    p_hover.add_argument("line", type=int, help="Line number (1-based)")
    p_hover.add_argument("col", type=int, help="Column number (1-based)")
    p_hover.set_defaults(func=cmd_hover)

    # definition
    p_def = sub.add_parser("definition", help="Go to definition")
    p_def.add_argument("file", help="Kotlin file path")
    p_def.add_argument("line", type=int, help="Line number (1-based)")
    p_def.add_argument("col", type=int, help="Column number (1-based)")
    p_def.set_defaults(func=cmd_definition)

    # references
    p_ref = sub.add_parser("references", help="Find all references")
    p_ref.add_argument("file", help="Kotlin file path")
    p_ref.add_argument("line", type=int, help="Line number (1-based)")
    p_ref.add_argument("col", type=int, help="Column number (1-based)")
    p_ref.set_defaults(func=cmd_references)

    # symbols
    p_sym = sub.add_parser("symbols", help="List symbols in file or workspace")
    p_sym.add_argument("file", nargs="?", help="Kotlin file path")
    p_sym.add_argument("--query", "-q", help="Workspace symbol search query")
    p_sym.set_defaults(func=cmd_symbols)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    try:
        code = asyncio.run(args.func(args))
    except KeyboardInterrupt:
        code = 130
    except Exception as exc:
        logger.debug("Unhandled error", exc_info=True)
        print(f"Error: {exc}", file=sys.stderr)
        code = 2

    sys.exit(code)
