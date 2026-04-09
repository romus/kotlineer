# kotlineer

Lightweight Python CLI and library for [JetBrains kotlin-lsp](https://github.com/Kotlin/kotlin-lsp). Run diagnostics, format code, navigate symbols and more — directly from the terminal.

## Prerequisites

### 1. Install kotlin-lsp

Requires **Java 17+**.

**macOS (Homebrew):**

```bash
brew install JetBrains/utils/kotlin-lsp
```

**Manual install:**

Download the latest release from [GitHub Releases](https://github.com/Kotlin/kotlin-lsp/releases), unpack it, and add to your PATH.

### 2. Install kotlineer

```bash
pip install kotlineer
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install kotlineer
```

## Quick start

Start kotlin-lsp in socket mode (default port 8200):

```bash
kotlin-lsp --socket 8200
```

Then in another terminal, navigate to your Kotlin project and run:

```bash
cd ~/projects/my-spring-app
kotlineer check
```

By default kotlineer connects to a running kotlin-lsp at `localhost:8200`. This is faster than spawning a new process each time and allows sharing the server across tools.

Output:

```
src/main/kotlin/com/example/UserService.kt:15:9: error: Unresolved reference: userRepo
src/main/kotlin/com/example/AppConfig.kt:8:1: warning: Unused import directive
```

Exit code is `1` if there are issues, `0` if clean.

### Spawning a server on the fly

If you prefer to launch a fresh server for each invocation (slower but no setup):

```bash
kotlineer --spawn check
```

## Usage

### Check files for errors

```bash
# Check all .kt files in the current project
kotlineer check

# Check specific files
kotlineer check src/main/kotlin/com/example/UserService.kt

# Only errors (ignore warnings)
kotlineer check --errors-only

# JSON output (for CI/tooling)
kotlineer check --json

# Increase settle time for large projects
kotlineer check --settle-time 10
```

### Format code

```bash
# Format all .kt files in-place
kotlineer format

# Format specific files
kotlineer format src/main/kotlin/com/example/UserService.kt

# Dry-run: check if files need formatting (exit 1 if yes — useful in CI)
kotlineer format --check

# Show diff without writing
kotlineer format --diff
```

### Get type info (hover)

```bash
# Get type/documentation at line 15, column 9 (1-based)
kotlineer hover src/main/kotlin/com/example/UserService.kt 15 9
```

### Go to definition

```bash
kotlineer definition src/main/kotlin/com/example/UserService.kt 15 9
# Output: /abs/path/to/UserRepository.kt:8:5
```

### Find references

```bash
kotlineer references src/main/kotlin/com/example/UserRepository.kt 8 14
# Output:
# /abs/path/to/UserService.kt:15:9
# /abs/path/to/UserServiceTest.kt:22:13
```

### List symbols

```bash
# Symbols in a file
kotlineer symbols src/main/kotlin/com/example/UserService.kt
# Output:
# Class UserService  (line 10)
#   Method findById  (line 14)
#   Method save  (line 20)

# Search across the workspace
kotlineer symbols --query UserService
```

## Global options

| Option | Description |
|--------|-------------|
| `--connect HOST:PORT` | Connect to a running kotlin-lsp server (default: `localhost:8200`) |
| `--spawn` | Launch a new kotlin-lsp subprocess instead of connecting |
| `--server-path PATH` | Path to `kotlin-lsp` binary, used with `--spawn` (env: `KOTLINEER_SERVER`) |
| `-w, --workspace DIR` | Project root directory (default: current directory) |
| `--timeout SECONDS` | Request timeout (default: 30) |
| `--json` | Output as JSON |
| `-v, --verbose` | Enable debug logging |

### Examples with options

```bash
# Connect to a server on a custom host/port
kotlineer --connect 10.0.0.5:9090 check

# Spawn a new server process
kotlineer --spawn check

# Spawn with a custom server path
kotlineer --spawn --server-path /opt/kls/bin/kotlin-lsp check

# Via environment variable (for --spawn mode)
export KOTLINEER_SERVER=/opt/kls/bin/kotlin-lsp
kotlineer --spawn check

# Different workspace
kotlineer -w ~/projects/my-spring-app check

# Verbose mode for debugging
kotlineer -v check src/main/kotlin/com/example/App.kt
```

## CI example

```yaml
# GitHub Actions
- name: Start kotlin-lsp
  run: kotlin-lsp --socket 8200 &

- name: Check Kotlin code
  run: |
    kotlineer check --errors-only
    kotlineer format --check
```

## Using as a library

### Connect to a running server (default)

```python
import asyncio
from kotlineer import KotlinLspClient

async def main():
    # Connects to kotlin-lsp at localhost:8200
    client = KotlinLspClient("/path/to/my-spring-app")

    await client.start()

    uri = await client.open_file("src/main/kotlin/com/example/UserService.kt")

    # Diagnostics
    diags = client.diagnostics.get()

    # Hover
    info = await client.hover.hover(uri, line=14, character=8)

    # Go to definition
    loc = await client.navigation.definition(uri, line=14, character=8)

    # Completion
    items = await client.completion.complete(uri, line=14, character=8)

    # Format
    edits = await client.formatting.format(uri)

    await client.stop()

asyncio.run(main())
```

### Custom host/port

```python
client = KotlinLspClient("/path/to/project", host="10.0.0.5", port=9090)
```

### Spawn a new server subprocess

```python
client = KotlinLspClient.spawn("/path/to/project")
# or with a custom binary
client = KotlinLspClient.spawn("/path/to/project", server_path="/opt/kls/bin/kotlin-lsp")
```
