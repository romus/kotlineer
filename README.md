# kotlineer

Lightweight Python CLI and library for [JetBrains kotlin-lsp](https://github.com/Kotlin/kotlin-lsp). Run diagnostics, format code, navigate symbols and more — directly from the terminal, Python code, or AI assistants via MCP.

## Prerequisites

- **Java 17+**
- **kotlin-lsp**: `brew install JetBrains/utils/kotlin-lsp` ([manual install](https://github.com/Kotlin/kotlin-lsp/releases))
- **Python 3.11+**

## Install

### Homebrew (macOS)

```bash
brew tap romkln/tap
brew install kotlineer
```

### pip

```bash
pip install kotlineer
```

## Quick Start

```bash
# Start kotlin-lsp in background
kotlin-lsp --socket 8200

# Run diagnostics and formatting
kotlineer check                    # diagnostics on all .kt files
kotlineer format                   # format all .kt files in place
kotlineer format --check           # check formatting (CI-friendly, exit 1 if unformatted)

# Navigate code
kotlineer hover Main.kt 15 9      # type info at line 15, col 9
kotlineer definition Main.kt 15 9 # go to definition
kotlineer references Main.kt 8 14 # find all references
kotlineer symbols Main.kt         # list symbols in file
kotlineer symbols -q UserService   # search workspace symbols
```

All commands accept `--json` for machine-readable output. Use `--spawn` to launch kotlin-lsp automatically (no pre-running server needed).

See [CLI Reference](docs/cli.md) for all commands and options.

## Library Usage

```python
import asyncio
from kotlineer import KotlinLspClient

async def main():
    client = KotlinLspClient("/path/to/project")
    await client.start()

    uri = await client.open_file("src/main/kotlin/App.kt")

    diags   = client.diagnostics.get()
    info    = await client.hover.hover(uri, line=14, character=8)
    loc     = await client.navigation.definition(uri, line=14, character=8)
    edits   = await client.formatting.format(uri)
    refs    = await client.navigation.references(uri, line=14, character=8)

    await client.stop()

asyncio.run(main())
```

See [Library Reference](docs/library.md) for the full API.

## MCP Server

kotlineer exposes kotlin-lsp as tools for AI assistants (Claude Code, Claude Desktop, etc.) via [MCP](https://modelcontextprotocol.io).

Add to `.mcp.json` in your Kotlin project:

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

See [MCP Server docs](docs/mcp.md) for all available tools and configuration options.

## Documentation

| Document | Description |
|----------|-------------|
| [Quick Start](docs/quickstart.md) | Install, run, and check your first Kotlin file in 5 minutes |
| [CLI Reference](docs/cli.md) | All commands, options, flags, and output formats |
| [Library Reference](docs/library.md) | Full Python API: client construction, services, error handling |
| [MCP Server](docs/mcp.md) | MCP tools for AI assistants |
| [Use Cases](docs/use-cases.md) | CI/CD, pre-commit hooks, code analysis, batch refactoring |
| [Architecture](docs/architecture.md) | Internal design, layer diagram, connection modes |

## CI Example

```yaml
- name: Start kotlin-lsp
  run: kotlin-lsp --socket 8200 &

- name: Lint & format check
  run: |
    kotlineer check --errors-only
    kotlineer format --check
```
