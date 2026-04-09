# kotlineer

Lightweight Python CLI and library for [JetBrains kotlin-lsp](https://github.com/Kotlin/kotlin-lsp). Run diagnostics, format code, navigate symbols and more — directly from the terminal or Python code.

## Prerequisites

- **Java 17+**
- **kotlin-lsp**: `brew install JetBrains/utils/kotlin-lsp` ([manual install](https://github.com/Kotlin/kotlin-lsp/releases))
- **Python 3.11+**

## Install

```bash
pip install kotlineer
```

## Quick Start

Start kotlin-lsp in socket mode (runs in background):

```bash
kotlin-lsp --socket 8200
```

Then use kotlineer — it connects to the running server automatically:

```bash
kotlineer check                    # run diagnostics on all .kt files
kotlineer format                   # format all .kt files in place
kotlineer format --check           # check formatting (CI-friendly, exit 1 if unformatted)
kotlineer hover Main.kt 15 9      # type info at line 15, col 9
kotlineer definition Main.kt 15 9 # go to definition
kotlineer references Main.kt 8 14 # find all references
kotlineer symbols Main.kt         # list symbols in file
kotlineer symbols -q UserService   # search workspace symbols
```

All commands accept `--json` for machine-readable output.

### Spawn mode (no pre-running server)

```bash
kotlineer --spawn check
```

## Library Usage

```python
import asyncio
from kotlineer import KotlinLspClient

async def main():
    # Connect to running server (default: localhost:8200)
    client = KotlinLspClient("/path/to/project")
    await client.start()

    uri = await client.open_file("src/main/kotlin/App.kt")

    diags   = client.diagnostics.get()
    info    = await client.hover.hover(uri, line=14, character=8)
    loc     = await client.navigation.definition(uri, line=14, character=8)
    items   = await client.completion.complete(uri, line=14, character=8)
    edits   = await client.formatting.format(uri)
    refs    = await client.navigation.references(uri, line=14, character=8)
    actions = await client.code_actions.get_actions(uri, 0, 0, 10, 0)

    await client.stop()

asyncio.run(main())
```

Or spawn a subprocess:

```python
client = KotlinLspClient.spawn("/path/to/project")
```

## Documentation

| Document | Description |
|----------|-------------|
| [CLI Reference](docs/cli.md) | All commands, options, flags, and output formats |
| [Library Reference](docs/library.md) | Full Python API: client construction, services, error handling |
| [Use Cases](docs/use-cases.md) | CI/CD, pre-commit hooks, code analysis, batch refactoring, multi-project setups |
| [Architecture](docs/architecture.md) | Internal design, layer diagram, connection modes |

## Global Options

| Option | Default | Description |
|--------|---------|-------------|
| `--connect HOST:PORT` | `localhost:8200` | Connect to a running kotlin-lsp |
| `--spawn` | off | Launch a new subprocess instead |
| `--server-path PATH` | `kotlin-lsp` | Binary path (with `--spawn`) |
| `-w, --workspace DIR` | `.` | Project root |
| `--timeout SEC` | `30` | Request timeout |
| `--json` | off | JSON output |
| `-v` | off | Verbose / debug logging |

## CI Example

```yaml
- name: Start kotlin-lsp
  run: kotlin-lsp --socket 8200 &

- name: Lint & format check
  run: |
    kotlineer check --errors-only
    kotlineer format --check
```
