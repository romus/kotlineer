# kotlineer

Lightweight Python CLI and library for [kotlin-language-server](https://github.com/fwcd/kotlin-language-server). Run diagnostics, format code, navigate symbols and more — directly from the terminal.

## Prerequisites

### 1. Install kotlin-language-server

**macOS (Homebrew):**

```bash
brew install kotlin-language-server
```

**Manual install:**

```bash
# Download the latest release
curl -L -o kls.zip https://github.com/fwcd/kotlin-language-server/releases/latest/download/server.zip
unzip kls.zip -d kotlin-language-server
export PATH="$PWD/kotlin-language-server/bin:$PATH"
```

Verify the installation:

```bash
kotlin-language-server --version
```

### 2. Install kotlineer

```bash
pip install kotlineer
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv pip install kotlineer
```

## Quick start

Navigate to your Kotlin/Spring Boot project and run a check:

```bash
cd ~/projects/my-spring-app
kotlineer check
```

This will start kotlin-language-server, analyze all `.kt` files in the project and print diagnostics in a familiar format:

```
src/main/kotlin/com/example/UserService.kt:15:9: error: Unresolved reference: userRepo
src/main/kotlin/com/example/AppConfig.kt:8:1: warning: Unused import directive
```

Exit code is `1` if there are issues, `0` if clean.

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
| `--server-path PATH` | Path to `kotlin-language-server` binary (env: `KOTLINEER_SERVER`) |
| `-w, --workspace DIR` | Project root directory (default: current directory) |
| `--timeout SECONDS` | Request timeout (default: 30) |
| `--json` | Output as JSON |
| `-v, --verbose` | Enable debug logging |

### Examples with options

```bash
# Custom server path
kotlineer --server-path /opt/kls/bin/kotlin-language-server check

# Via environment variable
export KOTLINEER_SERVER=/opt/kls/bin/kotlin-language-server
kotlineer check

# Different workspace
kotlineer -w ~/projects/my-spring-app check

# Verbose mode for debugging
kotlineer -v check src/main/kotlin/com/example/App.kt
```

## CI example

```yaml
# GitHub Actions
- name: Check Kotlin code
  run: |
    kotlineer check --errors-only
    kotlineer format --check
```

## Using as a library

```python
import asyncio
from kotlineer import KotlinLspClient

async def main():
    client = KotlinLspClient(
        server_path="kotlin-language-server",
        workspace_root="/path/to/my-spring-app",
    )

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
