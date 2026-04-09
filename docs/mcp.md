# MCP Server

kotlineer includes an MCP (Model Context Protocol) server that exposes kotlin-lsp capabilities as tools for AI assistants like Claude Desktop, Claude Code, and other MCP-compatible clients.

## Setup

### Claude Code

Add to your Kotlin project's `.mcp.json`:

```json
{
  "mcpServers": {
    "kotlineer": {
      "command": "kotlineer-mcp",
      "args": ["--workspace", "."]
    }
  }
}
```

Or configure globally in `~/.claude.json`:

```json
{
  "mcpServers": {
    "kotlineer": {
      "command": "kotlineer-mcp",
      "args": ["--workspace", "/path/to/kotlin-project"]
    }
  }
}
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "kotlineer": {
      "command": "kotlineer-mcp",
      "args": ["--workspace", "/path/to/kotlin-project"]
    }
  }
}
```

### Other MCP Clients

Run the server directly:

```bash
kotlineer-mcp --workspace /path/to/kotlin-project
```

The server communicates over stdio using the MCP protocol.

## Server Options

| Option | Default | Description |
|--------|---------|-------------|
| `-w`, `--workspace` | `.` (cwd) | Project root directory. Also settable via `KOTLINEER_WORKSPACE` env var. |
| `--server-path` | `kotlin-lsp` | Path to kotlin-lsp binary. Also settable via `KOTLINEER_SERVER` env var. |
| `--connect` | (none) | Connect to a running kotlin-lsp at `host:port` instead of spawning a new one. |
| `--timeout` | `30` | LSP request timeout in seconds. |

### Running with a pre-started server

If you already have kotlin-lsp running (e.g., `kotlin-lsp --socket 8200`), use `--connect`:

```json
{
  "mcpServers": {
    "kotlineer": {
      "command": "kotlineer-mcp",
      "args": ["--workspace", ".", "--connect", "localhost:8200"]
    }
  }
}
```

This skips spawning a subprocess and connects to the existing server.

## Available Tools

### kotlin_check

Check Kotlin files for errors and warnings.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `files` | `list[str]` | all `.kt` files | File paths to check |
| `errors_only` | `bool` | `false` | Only report errors |

Returns JSON with diagnostics grouped by file (line, column, severity, message).

### kotlin_format

Format a Kotlin file.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | `str` | (required) | File path to format |
| `write` | `bool` | `false` | Write formatted content back to disk |

Returns formatted file content, or a message if no changes needed.

### kotlin_hover

Get type information and documentation at a position.

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | `str` | File path |
| `line` | `int` | Line number (1-based) |
| `column` | `int` | Column number (1-based) |

Returns type info and documentation as text/markdown.

### kotlin_definition

Go to the definition of a symbol.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file` | `str` | (required) | File path |
| `line` | `int` | (required) | Line number (1-based) |
| `column` | `int` | (required) | Column number (1-based) |
| `kind` | `str` | `"definition"` | `"definition"` or `"type_definition"` |

Returns JSON list of locations (file, line, column).

### kotlin_references

Find all references to a symbol.

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | `str` | File path |
| `line` | `int` | Line number (1-based) |
| `column` | `int` | Column number (1-based) |

Returns JSON list of locations.

### kotlin_symbols

List symbols in a file or search across the workspace.

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | `str` | File path (for document symbols) |
| `query` | `str` | Search query (for workspace-wide search) |

Provide either `file` or `query`. Returns JSON list of symbols.

### kotlin_complete

Get code completion suggestions at a position.

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | `str` | File path |
| `line` | `int` | Line number (1-based) |
| `column` | `int` | Column number (1-based) |

Returns JSON list of completion items (label, kind, detail).

### kotlin_rename

Rename a symbol across the project.

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | `str` | File path containing the symbol |
| `line` | `int` | Line number (1-based) |
| `column` | `int` | Column number (1-based) |
| `new_name` | `str` | New name for the symbol |

Returns JSON summary of the workspace edit (files changed and edits per file).

## CLI Subcommand

The MCP server can also be started via the `kotlineer` CLI:

```bash
kotlineer mcp --workspace /path/to/kotlin-project
```

This is equivalent to running `kotlineer-mcp` directly.
