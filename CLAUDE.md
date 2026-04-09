# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is kotlineer

A Python CLI and library wrapping JetBrains kotlin-lsp. Provides diagnostics, formatting, hover, go-to-definition, references, symbols, and more via LSP over TCP socket or spawned subprocess.

## Build & Development Commands

```bash
make install-dev      # install with dev deps (uv sync --extra dev)
make test             # run all tests
make test-unit        # unit tests only (excludes integration)
make test-integration # integration tests only
make lint             # ruff check
make lint-fix         # ruff check --fix
make fmt              # ruff format
make typecheck        # mypy src/
make check            # fmt-check + lint + typecheck + test (CI gate)
make pipx-install     # build wheel and install via pipx
```

Run a single test: `uv run python -m pytest tests/test_cli.py -v -k "test_name"`

## Architecture

**Layered design:**

1. **`connection.py`** — JSON-RPC transport over LSP Content-Length framing. Handles request/response matching, notification dispatch, and timeouts.
2. **`client.py`** — `KotlinLspClient` facade. Two connection modes: TCP socket (constructor) or spawned subprocess (`KotlinLspClient.spawn()`). Manages LSP lifecycle (initialize/shutdown), document open/close, and lazy service creation.
3. **`services/`** — One service per LSP capability (diagnostics, formatting, hover, navigation, symbols, completion, code_actions, refactoring, hierarchy, jetbrains_extensions). Each takes an `LspConnection` and wraps raw LSP methods.
4. **`cli.py`** — argparse-based CLI entry point (`kotlineer` command). Each subcommand is an async function (`cmd_check`, `cmd_format`, etc.) that creates a client, runs operations, and formats output.

5. **`mcp_server.py`** — MCP server (`FastMCP`) exposing kotlin-lsp as 8 MCP tools for AI assistants. Uses `KotlinLspClient` via lifespan context. Entry point: `kotlineer-mcp` or `kotlineer mcp`.
6. **`utils.py`** — Shared utilities used by both CLI and MCP server (text edits, URI conversion, file discovery, diagnostics waiting).

**Supporting modules:** `types.py` (config dataclass, error classes), `documents.py` (document open/close/update tracking), `process.py` (subprocess management).

**Key patterns:**
- All LSP communication is async (asyncio). Tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
- Services are lazily instantiated via `_get_service()` and cached on the client.
- CLI converts 1-based user input (line/col) to 0-based LSP positions.
- `--connect host:port` for external server, `--spawn` for subprocess mode (default in CLI uses spawn unless `--connect` is given).

## Tool Configuration

- **Linter/formatter:** ruff (line-length=100, target py311, rules: E/F/I/UP)
- **Type checker:** mypy (strict=false, warn_return_any=true)
- **Build:** hatchling with uv
- **Python:** >=3.11
