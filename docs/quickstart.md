# Quick Start Guide

Get kotlineer running and check your first Kotlin file in under 5 minutes.

## 1. Install Prerequisites

### Java 17+

```bash
# macOS
brew install openjdk@17

# Verify
java -version
```

### kotlin-lsp

```bash
# macOS (Homebrew)
brew install JetBrains/utils/kotlin-lsp

# Or download manually from:
# https://github.com/Kotlin/kotlin-lsp/releases
```

### kotlineer

```bash
pip install kotlineer
# or
uv pip install kotlineer
```

## 2. Start kotlin-lsp Server

Open a terminal and start the language server in socket mode:

```bash
kotlin-lsp --socket 8200
```

Leave this running. The server stays warm between requests, making subsequent calls fast.

> **Tip:** Add `&` to run it in the background: `kotlin-lsp --socket 8200 &`

## 3. Check a Kotlin File

```bash
# Check all .kt files in current directory
kotlineer check

# Check a specific file
kotlineer check src/main/kotlin/App.kt

# Check multiple files
kotlineer check App.kt Utils.kt

# Specify project root with -w (workspace)
kotlineer -w /path/to/your/kotlin-project check

# Combine: project root + specific file
kotlineer -w /path/to/your/kotlin-project check src/main/kotlin/App.kt

# Show only errors (skip warnings)
kotlineer check --errors-only
```

> **Note:** `-w` (or `--workspace`) sets the project root for kotlin-lsp. Without it, kotlineer uses the current directory. The file paths are relative to the workspace.

Example output:

```
src/main/kotlin/App.kt:12:5  error  Unresolved reference: foo
src/main/kotlin/App.kt:25:1  warn   Unused variable 'x'

Found 2 issues in 1 file (1 error, 1 warning)
```

Exit codes: `0` = no issues, `1` = issues found, `2` = error.

## 4. Format Kotlin Files

```bash
# Format all .kt files in place
kotlineer format

# Dry-run: check if files are formatted (useful in CI)
kotlineer format --check

# Show diff of what would change
kotlineer format --diff
```

## 5. Explore Code

```bash
# Type info at line 15, column 9
kotlineer hover Main.kt 15 9

# Jump to definition
kotlineer definition Main.kt 15 9

# Find all references
kotlineer references Main.kt 8 14

# List symbols in a file
kotlineer symbols Main.kt

# Search symbols across the project
kotlineer symbols -q UserService
```

## 6. JSON Output

Add `--json` to any command for machine-readable output:

```bash
kotlineer check --json
kotlineer symbols Main.kt --json
```

## Alternative: Spawn Mode

If you don't want to keep a server running, use `--spawn` to start a temporary kotlin-lsp process per invocation:

```bash
kotlineer --spawn check
kotlineer --spawn format --check
```

This is simpler but slower — each call starts a fresh server. Prefer the socket mode for interactive use and repeated checks.

## Common Workflows

### Pre-commit hook

```bash
#!/bin/sh
kotlineer check --errors-only || exit 1
kotlineer format --check || exit 1
```

### CI/CD (GitHub Actions)

```yaml
- name: Install
  run: |
    brew install JetBrains/utils/kotlin-lsp
    pip install kotlineer

- name: Start kotlin-lsp
  run: kotlin-lsp --socket 8200 &

- name: Check
  run: |
    kotlineer check --errors-only
    kotlineer format --check
```

## 7. MCP for AI Assistants

kotlineer includes an MCP server for use with Claude Desktop, Claude Code, and other MCP-compatible AI assistants.

### Claude Code

Add `.mcp.json` to your Kotlin project:

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

This gives the AI assistant 8 Kotlin tools: check, format, hover, definition, references, symbols, completion, and rename.

See [MCP Server](mcp.md) for full documentation.

## Next Steps

- [CLI Reference](cli.md) — all commands, options, and output formats
- [MCP Server](mcp.md) — use kotlineer with AI assistants
- [Library Reference](library.md) — use kotlineer as a Python library
- [Use Cases](use-cases.md) — CI/CD, batch refactoring, code analysis patterns
- [Architecture](architecture.md) — internal design and how it works
